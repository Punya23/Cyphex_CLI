"""Static security knowledge base loader for CWE fix strategies."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any, Optional


@dataclass
class Strategy:
    name: str
    pattern: str
    applies_to: list[str]


class SecurityKB:
    def __init__(self, payload: dict[str, Any]):
        self.payload = payload or {}
        self.kb_version = self.payload.get("kb_version", "unknown")
        self._cwe = self.payload.get("cwe", {})

    def get(self, cwe: str) -> dict[str, Any]:
        return self._cwe.get((cwe or "").upper(), {})

    def primary_strategy(self, cwe: str) -> Optional[Strategy]:
        item = self.get(cwe)
        strategies = item.get("fix_strategies", [])
        if not strategies:
            return None
        first = strategies[0]
        return Strategy(
            name=str(first.get("name", "")),
            pattern=str(first.get("pattern", "")),
            applies_to=list(first.get("applies_to", [])),
        )

    def anti_patterns(self, cwe: str) -> list[str]:
        item = self.get(cwe)
        return list(item.get("anti_patterns", []))


def load_security_kb(base_dir: Optional[str] = None) -> SecurityKB:
    here = base_dir or os.path.dirname(__file__)
    path = os.path.join(here, "security_kb.json")
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        data = {"kb_version": "missing", "cwe": {}}
    return SecurityKB(data)
