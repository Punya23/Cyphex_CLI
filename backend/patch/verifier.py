"""
verifier.py — the verification gate. A patch is "fixed" only when MEASURED fixed.

Two branches:
  static  — re-run the scanner scoped to the patched file; the finding must be
            gone (no sandbox needed; covers the majority of findings).
  dynamic — replay the original exploit against the running app and confirm it
            no longer works AND the endpoint is still alive.

Plus two anti-gaming guards applied to every patch:
  anti-suppression — reject diffs that just add nosemgrep / eslint-disable /
                     # noqa / @ts-ignore (suppress the warning, don't fix it).
  blast-radius     — reject diffs larger than a cap (route deletions, rewrites)
                     so they go to human review instead of silent auto-accept.

verdict == "PASS" requires every applicable check to pass. When the relevant
verifier cannot run (no scanner, can't reach the app), verdict == "UNVERIFIABLE"
and the patch is recorded as applied-unverified — never counted as fixed.
"""

from __future__ import annotations

import difflib
import re
from dataclasses import dataclass, field
from typing import Optional

PASS = "PASS"
FAIL = "FAIL"
UNVERIFIABLE = "UNVERIFIABLE"

DEFAULT_BLAST_CAP = 40

_SUPPRESSION_PATTERNS = [
    r"nosemgrep",
    r"eslint-disable",
    r"#\s*noqa",
    r"@ts-ignore",
    r"@ts-nocheck",
    r"@SuppressWarnings",
    r"//\s*NOSONAR",
    r"#\s*type:\s*ignore",
    r"#\s*pylint:\s*disable",
]


@dataclass
class VerifyResult:
    kind: str               # "static" | "dynamic" | "none"
    finding_gone: bool
    builds: bool
    endpoint_alive: bool
    no_suppression: bool
    blast_ok: bool
    verdict: str            # PASS | FAIL | UNVERIFIABLE
    evidence: dict = field(default_factory=dict)

    @property
    def passed(self) -> bool:
        return self.verdict == PASS


# ── guards ──────────────────────────────────────────────────────────────────
def check_suppression(original: str, patched: str) -> tuple[bool, dict]:
    """False if the patch ADDS a suppression marker that wasn't there before."""
    added = []
    for pat in _SUPPRESSION_PATTERNS:
        before = len(re.findall(pat, original, re.IGNORECASE))
        after = len(re.findall(pat, patched, re.IGNORECASE))
        if after > before:
            added.append(pat)
    ok = not added
    return ok, ({} if ok else {"suppression_added": added})


def changed_line_count(original: str, patched: str) -> int:
    """
    Honest count of how many lines a patch actually touches.

    Uses SequenceMatcher opcodes so a pure rewrite of N lines counts as N — NOT
    2N. The previous ndiff-based implementation summed '+' and '-' lines, which
    double-counted every rewrite and caused legitimate multi-line fixes (e.g. an
    SSRF/CMDi allowlist wrapper) to be falsely rejected as "blast radius too
    large".
    """
    o = original.splitlines()
    p = patched.splitlines()
    sm = difflib.SequenceMatcher(a=o, b=p)
    changed = 0
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "replace":
            changed += max(i2 - i1, j2 - j1)
        elif tag == "delete":
            changed += i2 - i1
        elif tag == "insert":
            changed += j2 - j1
    return changed


def check_blast_radius(original: str, patched: str, cap: int = DEFAULT_BLAST_CAP) -> tuple[bool, dict]:
    n = changed_line_count(original, patched)
    ok = n <= cap
    return ok, ({"changed_lines": n} if not ok else {"changed_lines": n})


# ── static branch ───────────────────────────────────────────────────────────
def _finding_still_present(findings, vuln, line: Optional[int]) -> bool:
    """
    True if a finding equivalent to `vuln` still exists in the re-scan.
    Match primarily by CWE, near the patched line (±2 for reflow tolerance).
    Falls back to vuln-name token match when CWE is unknown.
    """
    target_cwe = (getattr(vuln, "cwe", "") or "").strip().upper()
    name = (getattr(vuln, "name", "") or "").replace("[STATIC]", "").replace("[DYNAMIC]", "").strip().lower()

    for f in findings:
        f_cwe = (getattr(f, "cwe", "") or "").strip().upper()
        near = True
        if line is not None and getattr(f, "line_number", None):
            near = abs(f.line_number - line) <= 2
        if target_cwe and target_cwe != "CWE-UNKNOWN":
            if f_cwe == target_cwe and near:
                return True
        else:
            f_name = (getattr(f, "name", "") or "").lower()
            if name and (name in f_name or f_name in name) and near:
                return True
    return False


def verify_static(vuln, location, source_dir, original_text, patched_text,
                  blast_cap: int = DEFAULT_BLAST_CAP) -> VerifyResult:
    """
    Verify a static finding by re-scanning the patched file. `location` is a
    resolver.Location(kind="file"); original/patched_text are the file contents
    before/after the patch (for the guards).
    """
    no_suppression, sup_ev = check_suppression(original_text, patched_text)
    blast_ok, blast_ev = check_blast_radius(original_text, patched_text, blast_cap)

    evidence: dict = {}
    evidence.update(sup_ev)
    evidence.update(blast_ev)

    # Re-scan just this file.
    try:
        from cyphex import scanner
        findings = scanner.scan_single_file(location.file, source_dir)
    except Exception as e:  # scanner unusable → cannot verify
        evidence["scanner_error"] = str(e)[:160]
        return VerifyResult(
            kind="static", finding_gone=False, builds=True, endpoint_alive=True,
            no_suppression=no_suppression, blast_ok=blast_ok,
            verdict=UNVERIFIABLE, evidence=evidence,
        )

    still = _finding_still_present(findings, vuln, location.line)
    finding_gone = not still
    if still:
        evidence["finding_still_present"] = True

    verdict = PASS if (finding_gone and no_suppression and blast_ok) else FAIL
    return VerifyResult(
        kind="static", finding_gone=finding_gone, builds=True, endpoint_alive=True,
        no_suppression=no_suppression, blast_ok=blast_ok,
        verdict=verdict, evidence=evidence,
    )


# ── dynamic branch ──────────────────────────────────────────────────────────
_SQL_ERROR_SIGNS = [
    "sql syntax", "sqlite3.", "psql:", "mysql", "ora-0", "syntax error at or near",
    "unclosed quotation", "you have an error in your sql",
]


def _looks_exploited(status_code: int, body: str, vuln) -> bool:
    """Heuristic: does the response still show the exploit working?"""
    b = (body or "").lower()
    cwe = (getattr(vuln, "cwe", "") or "").upper()
    payload = (getattr(vuln, "payload", "") or "")

    # SQLi: SQL error leakage or previously-dumped data reappearing
    if "CWE-89" in cwe or "sql" in (getattr(vuln, "name", "") or "").lower():
        if any(sig in b for sig in _SQL_ERROR_SIGNS):
            return True
    # XSS: the raw payload reflected unescaped
    if "CWE-79" in cwe or "xss" in (getattr(vuln, "name", "") or "").lower():
        if payload and payload.lower() in b and "&lt;" not in b:
            return True
    # Generic: a previously dumped data / rce marker reappears
    dumped = (getattr(vuln, "dumped_data", "") or "").strip().lower()
    rce = (getattr(vuln, "rce_output", "") or "").strip().lower()
    for marker in (dumped, rce):
        if marker and len(marker) >= 6 and marker in b:
            return True
    return False


async def verify_dynamic(vuln, location, base_url: Optional[str],
                         original_text: str = "", patched_text: str = "",
                         blast_cap: int = DEFAULT_BLAST_CAP) -> VerifyResult:
    """
    Verify a dynamic finding by replaying the exploit against the running app.
    `base_url` is the live sandbox URL (already restarted with the patched file).
    Requires httpx; returns UNVERIFIABLE if the app can't be reached.
    """
    no_suppression, sup_ev = check_suppression(original_text, patched_text)
    blast_ok, blast_ev = check_blast_radius(original_text, patched_text, blast_cap)
    evidence: dict = {}
    evidence.update(sup_ev)
    evidence.update(blast_ev)

    url = location.url or base_url
    if not url:
        evidence["no_url"] = True
        return VerifyResult("dynamic", False, True, False, no_suppression, blast_ok,
                            UNVERIFIABLE, evidence)

    try:
        import httpx
    except ImportError:
        evidence["httpx_missing"] = True
        return VerifyResult("dynamic", False, True, False, no_suppression, blast_ok,
                            UNVERIFIABLE, evidence)

    method = (location.method or "GET").upper()
    payload = getattr(vuln, "payload", "") or ""

    try:
        async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
            # 1) Replay the exploit
            if method in ("POST", "PUT", "PATCH"):
                resp = await client.request(method, url, content=payload)
            else:
                sep = "&" if "?" in url else "?"
                replay_url = f"{url}{sep}{payload}" if payload else url
                resp = await client.request(method, replay_url)
            exploited = _looks_exploited(resp.status_code, resp.text, vuln)

            # 2) Liveness: a benign request must still work (< 500)
            live = await client.get(location.url or base_url)
            endpoint_alive = live.status_code < 500
    except Exception as e:
        evidence["request_error"] = str(e)[:160]
        return VerifyResult("dynamic", False, True, False, no_suppression, blast_ok,
                            UNVERIFIABLE, evidence)

    finding_gone = not exploited
    if exploited:
        evidence["exploit_still_works"] = True
    if not endpoint_alive:
        evidence["endpoint_dead"] = True

    verdict = PASS if (finding_gone and endpoint_alive and no_suppression and blast_ok) else FAIL
    return VerifyResult(
        kind="dynamic", finding_gone=finding_gone, builds=True,
        endpoint_alive=endpoint_alive, no_suppression=no_suppression,
        blast_ok=blast_ok, verdict=verdict, evidence=evidence,
    )
