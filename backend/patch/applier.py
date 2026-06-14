"""
applier.py — range-accurate, reversible patch application.

Replaces the old destructive apply in cli_engine._patch_workflow (bug R2):

    for j in range(start_l, end_l):   # blank every line in the window
        lines[j] = ""
    lines[start_l] = fixed + "\n"     # dump ALL fixed code onto line 1

That corrupts multi-line fixes and leaves stray blank lines. Here we do a
clean slice replacement of exactly the vulnerable span, take a backup first,
and expose rollback() + a cheap parse check so a syntactically broken patch is
reverted instead of left on disk.
"""

from __future__ import annotations

import os
import subprocess
import tempfile
from dataclasses import dataclass
from typing import Optional


@dataclass
class ApplyResult:
    ok: bool
    error: str = ""
    new_text: str = ""


class PatchApplier:
    """
    Apply a fixed code block to a file over a [start_l, end_l) line span
    (0-based, end-exclusive — the same convention cli_engine already computes).

    Usage:
        applier = PatchApplier(filepath)
        res = applier.apply_range(start_l, end_l, fixed_code)
        if not res.ok:
            ...  # already rolled back
        # later, to undo an accepted-then-rejected patch:
        applier.rollback()
    """

    def __init__(self, filepath: str):
        self.filepath = filepath
        self._backup: Optional[str] = None

    # ── public API ──────────────────────────────────────────────────────────
    def apply_range(self, start_l: int, end_l: int, fixed_code: str) -> ApplyResult:
        try:
            with open(self.filepath, "r", encoding="utf-8", errors="ignore") as f:
                original = f.read()
        except OSError as e:
            return ApplyResult(False, f"cannot read file: {e}")

        self._backup = original
        lines = original.splitlines(keepends=True)

        start_l = max(0, min(start_l, len(lines)))
        end_l = max(start_l, min(end_l, len(lines)))

        new_block = self._as_block(fixed_code, original)

        # ── Bracket-balance pre-check ──────────────────────────────────────
        # The snippet may be the *opening* of a multi-line handler.  If the
        # replacement closes more braces than the original, it will orphan
        # the remaining handler body and produce a syntax error.
        orig_span = "".join(lines[start_l:end_l])
        new_span  = "".join(new_block)
        orig_bal  = orig_span.count("{") - orig_span.count("}")
        new_bal   = new_span.count("{") - new_span.count("}")
        if orig_bal != new_bal:
            return ApplyResult(
                False,
                f"bracket-balance mismatch: original snippet has net depth "
                f"{orig_bal:+d}, replacement has {new_bal:+d}. "
                f"The snippet is only lines {start_l+1}–{end_l} of the file — "
                f"do NOT close braces/brackets that continue beyond the snippet boundary."
            )

        lines[start_l:end_l] = new_block
        new_text = "".join(lines)

        try:
            with open(self.filepath, "w", encoding="utf-8") as f:
                f.write(new_text)
        except OSError as e:
            self.rollback()
            return ApplyResult(False, f"cannot write file: {e}")

        ok, err = self._parse_check()
        if not ok:
            self.rollback()
            return ApplyResult(False, f"patch failed parse check: {err}")

        return ApplyResult(True, new_text=new_text)

    def rollback(self) -> bool:
        """Restore the file to its pre-patch contents. Returns True on success."""
        if self._backup is None:
            return False
        try:
            with open(self.filepath, "w", encoding="utf-8") as f:
                f.write(self._backup)
            return True
        except OSError:
            return False

    @property
    def backup(self) -> Optional[str]:
        return self._backup

    # ── helpers ─────────────────────────────────────────────────────────────
    @staticmethod
    def _as_block(fixed_code: str, original: str) -> list[str]:
        """
        Normalise the model's fixed code into a list of newline-terminated lines
        suitable for slice assignment. Strips a single trailing newline so we
        don't introduce a blank line, then re-adds terminators uniformly.
        """
        text = fixed_code.replace("\r\n", "\n").rstrip("\n")
        if text == "":
            return []
        return [ln + "\n" for ln in text.split("\n")]

    def _parse_check(self) -> tuple[bool, str]:
        """
        Cheap, best-effort syntax validation. Returns (True, "") when the file
        is either valid or not checkable (we never block on a missing toolchain).
        """
        ext = os.path.splitext(self.filepath)[1].lower()
        if ext == ".py":
            import py_compile
            try:
                py_compile.compile(self.filepath, doraise=True)
                return True, ""
            except py_compile.PyCompileError as e:
                return False, str(e).splitlines()[-1][:200]
            except Exception:
                return True, ""
        if ext in (".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx"):
            return self._node_check()
        return True, ""

    def _node_check(self) -> tuple[bool, str]:
        node = _which("node")
        if not node:
            return True, ""  # no toolchain → don't block
        # `node --check` only handles plain JS; for TS/JSX it will false-negative,
        # so we only hard-fail on plain .js/.mjs/.cjs where --check is reliable.
        ext = os.path.splitext(self.filepath)[1].lower()
        if ext not in (".js", ".mjs", ".cjs"):
            return True, ""
        try:
            with open(self.filepath, "r", encoding="utf-8", errors="ignore") as f:
                src = f.read()
            with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as tmp:
                tmp.write(src)
                tmp_path = tmp.name
            try:
                proc = subprocess.run(
                    [node, "--check", tmp_path],
                    capture_output=True, text=True, timeout=10,
                )
            finally:
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass
            if proc.returncode != 0:
                err_lines = (proc.stderr or "syntax error").strip().splitlines()
                # Node.js prints the version banner as the last line — skip it
                content = [l for l in err_lines if not l.startswith("Node.js ")]
                # Prefer the actual SyntaxError description
                syntax = [l for l in content if "SyntaxError" in l or "Error:" in l]
                msg = (syntax[-1] if syntax
                       else content[-1] if content
                       else err_lines[-1]).strip()[:200]
                return False, msg
            return True, ""
        except Exception:
            return True, ""


def _which(cmd: str) -> Optional[str]:
    from shutil import which
    return which(cmd)
