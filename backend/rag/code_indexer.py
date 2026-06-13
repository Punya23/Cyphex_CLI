"""Vectorless lexical code index for retrieval-augmented patch prompts."""

from __future__ import annotations

import os
import re
from collections import Counter
from dataclasses import dataclass
from typing import Any, Optional

_SKIP_DIRS = {
    ".git",
    "node_modules",
    "dist",
    "build",
    "__pycache__",
    ".venv",
    "venv",
}
_SKIP_EXT = {
    ".map", ".lock", ".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg",
    ".pdf", ".zip", ".gz", ".mp4", ".mp3", ".woff", ".woff2",
}
_SKIP_SUFFIX = (".min.js",)
_MAX_BYTES = 512 * 1024

_ROUTE_RE = re.compile(r"\b(app|router)\.(get|post|put|patch|delete|all)\s*\(\s*['\"]([^'\"]+)")
_PY_ROUTE_RE = re.compile(r"@\w*\.route\(\s*['\"]([^'\"]+)")
_IMPORT_RE = re.compile(r"^\s*(import\s+.+|from\s+.+\s+import\s+.+|const\s+.+\s*=\s*require\(.+\))\s*$", re.MULTILINE)
_FUNC_RE = re.compile(r"\b(function\s+[A-Za-z_][A-Za-z0-9_]*|def\s+[A-Za-z_][A-Za-z0-9_]*|async\s+def\s+[A-Za-z_][A-Za-z0-9_]*)")
_TOKEN_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]{2,}")

_DB_HINTS = ("select ", "insert ", "update ", "delete ", "sequelize", "prisma", "cursor.execute", "query(")
_AUTH_HINTS = ("jwt", "auth", "authorize", "isadmin", "bearer", "session", "role", "permission")


@dataclass
class IndexedFile:
    rel_path: str
    routes: list[str]
    has_db: bool
    has_auth: bool
    imports: list[str]
    functions: list[str]
    terms: Counter


class CodeIndexer:
    def __init__(self, source_dir: str):
        self.source_dir = source_dir
        self._files: list[IndexedFile] = []
        self._build()

    @property
    def files(self) -> list[IndexedFile]:
        return self._files

    def _should_skip(self, file_name: str) -> bool:
        lower = file_name.lower()
        ext = os.path.splitext(lower)[1]
        if ext in _SKIP_EXT:
            return True
        if any(lower.endswith(sfx) for sfx in _SKIP_SUFFIX):
            return True
        return False

    def _build(self) -> None:
        for root, dirs, files in os.walk(self.source_dir):
            dirs[:] = [d for d in dirs if d not in _SKIP_DIRS and not d.startswith(".")]
            for name in files:
                if self._should_skip(name):
                    continue
                fp = os.path.join(root, name)
                try:
                    if os.path.getsize(fp) > _MAX_BYTES:
                        continue
                    with open(fp, "r", encoding="utf-8", errors="ignore") as f:
                        content = f.read()
                except OSError:
                    continue

                rel = os.path.relpath(fp, self.source_dir)
                routes = [m.group(3) for m in _ROUTE_RE.finditer(content)]
                routes.extend([m.group(1) for m in _PY_ROUTE_RE.finditer(content)])

                imports = [m.group(1).strip() for m in _IMPORT_RE.finditer(content)]
                functions = [m.group(1).strip() for m in _FUNC_RE.finditer(content)]
                lower = content.lower()
                has_db = any(k in lower for k in _DB_HINTS)
                has_auth = any(k in lower for k in _AUTH_HINTS)
                terms = Counter(tok.lower() for tok in _TOKEN_RE.findall(content))

                self._files.append(
                    IndexedFile(
                        rel_path=rel,
                        routes=routes[:20],
                        has_db=has_db,
                        has_auth=has_auth,
                        imports=imports[:30],
                        functions=functions[:50],
                        terms=terms,
                    )
                )

    def find_for_vuln(self, vuln: Any, location: Any) -> list[str]:
        payload = (getattr(vuln, "payload", "") or "").lower()
        cwe = (getattr(vuln, "cwe", "") or "").upper()
        endpoint = (getattr(vuln, "endpoint", "") or "").lower()
        rel = (getattr(location, "rel", "") or "").lower()
        url = (getattr(location, "url", "") or "").lower()
        route_key = url or endpoint

        payload_terms = [t.lower() for t in _TOKEN_RE.findall(payload)[:10]]

        scored = []
        for f in self._files:
            s = 0
            lower_path = f.rel_path.lower()

            if rel and lower_path == rel:
                s += 12
            if route_key and any(r and r.lower() in route_key for r in f.routes):
                s += 10

            if cwe == "CWE-89" and f.has_db:
                s += 5
            if cwe in {"CWE-287", "CWE-306", "CWE-284"} and f.has_auth:
                s += 5
            if cwe in {"CWE-79", "CWE-918", "CWE-22", "CWE-942"} and (f.has_db or f.has_auth):
                s += 3

            if payload_terms:
                s += min(3, sum(1 for t in payload_terms if f.terms.get(t, 0) > 0))

            if s > 0:
                scored.append((s, f.rel_path))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [path for _, path in scored[:3]]

    def find_secure_pattern(self, cwe: str) -> Optional[str]:
        cwe = (cwe or "").upper()
        for f in self._files:
            text_terms = f.terms
            if cwe == "CWE-89" and (text_terms.get("placeholder", 0) or text_terms.get("parameterized", 0)):
                return f.rel_path
            if cwe in {"CWE-287", "CWE-306", "CWE-284"} and f.has_auth:
                return f.rel_path
            if cwe == "CWE-79" and (text_terms.get("sanitize", 0) or text_terms.get("escape", 0)):
                return f.rel_path
            if cwe == "CWE-918" and text_terms.get("allowlist", 0):
                return f.rel_path
        return None
