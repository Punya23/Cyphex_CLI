"""
resolver.py — single source of truth for "where does this vulnerability live?"

A `Vuln` (backend/backend/models/scan.py) stores its location in the free-text
`endpoint` field, in one of two shapes:

  static :  "relative/path/file.js:42"   → a source file + line
  dynamic:  "http://localhost:PORT/login" → a live URL, no source line

This module parses that field ONCE so every downstream consumer (applier,
verifier, manifest, regression) agrees on the location. The parsing mirrors the
logic that previously lived inline in cli_engine._patch_workflow.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional


@dataclass
class Location:
    kind: str                 # "file" | "url"
    file: Optional[str] = None   # absolute path on disk (kind == "file")
    rel: Optional[str] = None    # repo-relative path for display + manifest
    line: Optional[int] = None   # 1-based line number (kind == "file")
    url: Optional[str] = None    # full URL (kind == "url")
    method: str = "GET"          # HTTP method for dynamic findings

    @property
    def key(self) -> str:
        """Stable per-finding identity used by the manifest and tracking sets."""
        if self.kind == "file":
            return f"{self.rel}:{self.line}"
        return f"{self.method} {self.url}"


def _looks_like_url(endpoint: str) -> bool:
    return endpoint.startswith("http://") or endpoint.startswith("https://")


def resolve(vuln, source_dir: Optional[str]) -> Optional[Location]:
    """
    Resolve a Vuln into a Location, or None if it cannot be located on disk.

    - Dynamic (URL) findings return a Location(kind="url").
    - Static findings return Location(kind="file") with an absolute `file` that
      exists on disk. If the file cannot be found, returns None (caller treats
      it as non-patchable / dynamic-only).
    """
    endpoint = (getattr(vuln, "endpoint", "") or "").strip()
    if not endpoint:
        return None

    if _looks_like_url(endpoint):
        method = _infer_method(vuln)
        return Location(kind="url", url=endpoint, method=method)

    if ":" not in endpoint:
        return None

    parts = endpoint.split(":")
    rel_path = parts[0].strip()
    try:
        line = int(parts[1].split()[0])
    except (ValueError, IndexError):
        return None

    # Resolve against the scanned source dir first, then fall back to an
    # absolute path (semgrep emits full paths).
    filepath = None
    rel = rel_path
    if source_dir:
        candidate = os.path.join(source_dir, rel_path)
        if os.path.exists(candidate):
            filepath = candidate
    if filepath is None and os.path.exists(rel_path):
        filepath = rel_path
        if source_dir and os.path.isabs(rel_path) and rel_path.startswith(source_dir):
            rel = os.path.relpath(rel_path, source_dir)

    if filepath is None:
        return None

    return Location(kind="file", file=filepath, rel=rel, line=line)


def _infer_method(vuln) -> str:
    """Best-effort HTTP method from the vuln's recorded evidence/payload."""
    blob = " ".join(
        str(getattr(vuln, attr, "") or "")
        for attr in ("payload", "evidence", "attack_chain")
    ).upper()
    for m in ("DELETE", "PATCH", "PUT", "POST", "GET"):
        if m in blob:
            return m
    return "GET"
