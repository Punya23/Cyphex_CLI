"""
manifest.py — durable record of patch outcomes (.cyphex/patches.json).

Kills R4 (the assumed "after" score). The score is recomputed from VERIFIED
entries only; unverifiable/applied-unverified patches are recorded but excluded
from the durability metric so CYPHEX never shows a fake green.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Optional


MANIFEST_DIR = ".cyphex"
MANIFEST_FILE = "patches.json"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256(text: str) -> str:
    return hashlib.sha256((text or "").encode("utf-8", "ignore")).hexdigest()


@dataclass
class PatchRecord:
    key: str                  # f"{rel}:{line}:{cwe}" — stable per-finding id
    vuln_type: str
    cwe: str
    rel_path: str
    line: Optional[int]
    verdict: str              # "PASS" | "FAIL" | "UNVERIFIABLE"
    verified: bool            # True only when verdict == "PASS"
    patched_at: str = field(default_factory=_now)
    original_hash: str = ""
    patched_hash: str = ""
    exploit_payload: str = ""
    evidence: dict = field(default_factory=dict)


class PatchManifest:
    """Read/write .cyphex/patches.json under a project root."""

    def __init__(self, project_root: str):
        self.root = project_root
        self.dir = os.path.join(project_root, MANIFEST_DIR)
        self.path = os.path.join(self.dir, MANIFEST_FILE)
        self.records: dict[str, dict] = {}
        self._load()

    def _load(self) -> None:
        if os.path.exists(self.path):
            try:
                with open(self.path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self.records = {r["key"]: r for r in data.get("patches", [])}
            except (OSError, ValueError, KeyError):
                self.records = {}

    def save(self) -> None:
        try:
            os.makedirs(self.dir, exist_ok=True)
            payload = {
                "version": 1,
                "updated_at": _now(),
                "patches": list(self.records.values()),
            }
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2)
        except OSError:
            pass

    def record(self, rec: PatchRecord) -> None:
        self.records[rec.key] = asdict(rec)

    def get(self, key: str) -> Optional[dict]:
        return self.records.get(key)

    def verified_keys(self) -> set[str]:
        """Keys whose patch was objectively verified as fixing the finding."""
        return {k for k, r in self.records.items() if r.get("verified")}

    @staticmethod
    def make_key(rel_path: str, line: Optional[int], cwe: str) -> str:
        return f"{rel_path}:{line}:{cwe}"
