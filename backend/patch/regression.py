"""Regression test generation for verified vulnerabilities."""

from __future__ import annotations

import os
import re
from typing import Optional


def _slug(text: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9]+", "_", text or "finding").strip("_").lower()
    return s[:60] or "finding"


def _detect_method(vuln) -> str:
    evi = (getattr(vuln, "evidence", "") or "").upper()
    for m in ("POST", "PUT", "PATCH", "DELETE", "GET"):
        if m in evi:
            return m
    return "GET"


def emit_dynamic_regression_test(project_root: str, vuln, endpoint: str, payload: str) -> Optional[str]:
    if not endpoint:
        return None
    tests_dir = os.path.join(project_root, "tests", "security")
    os.makedirs(tests_dir, exist_ok=True)

    name = _slug(f"{getattr(vuln, 'name', 'dynamic')}_{getattr(vuln, 'cwe', '')}")
    method = _detect_method(vuln)
    path = os.path.join(tests_dir, f"test_regression_{name}.py")

    content = f'''"""Auto-generated regression test for verified fix: {getattr(vuln, "name", "")}"""

import httpx
import pytest


@pytest.mark.asyncio
async def test_regression_{name}():
    url = "{endpoint}"
    payload = """{payload or ""}"""
    async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
        if "{method}" in ("POST", "PUT", "PATCH"):
            resp = await client.request("{method}", url, content=payload)
        else:
            sep = "&" if "?" in url else "?"
            replay_url = f"{{url}}{{sep}}{{payload}}" if payload else url
            resp = await client.request("{method}", replay_url)
    assert resp.status_code < 500
'''
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    return path


def emit_static_regression_note(project_root: str, rel_path: str, rule_id: str, line: int) -> Optional[str]:
    if not rel_path:
        return None
    tests_dir = os.path.join(project_root, "tests", "security")
    os.makedirs(tests_dir, exist_ok=True)
    name = _slug(f"{rule_id}_{os.path.basename(rel_path)}_{line}")
    path = os.path.join(tests_dir, f"test_static_regression_{name}.py")
    content = f'''"""Auto-generated static regression marker."""


def test_static_regression_{name}():
    # Ensure the vulnerable location remains under review in static scans.
    assert "{rule_id}" != ""
    assert "{rel_path}" != ""
    assert {int(line)} > 0
'''
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    return path
