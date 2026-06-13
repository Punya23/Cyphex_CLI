"""Deterministic template transforms for common CWE classes."""

from __future__ import annotations

import os
import re
from typing import Optional


def _lang_from_path(file_path: str) -> str:
    ext = os.path.splitext((file_path or "").lower())[1]
    if ext in {".py"}:
        return "python"
    if ext in {".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs"}:
        return "javascript"
    return "text"


def _template_sqli(snippet: str, lang: str) -> Optional[str]:
    if lang == "python" and "execute(" in snippet and "%" in snippet:
        return re.sub(r"execute\((.+?)%\s*(.+?)\)", r"execute(\1, \2)", snippet)
    if "SELECT" in snippet.upper() and ("+" in snippet or "${" in snippet or "`" in snippet):
        return (
            "const query = 'SELECT * FROM users WHERE id = ?';\n"
            "const result = await db.query(query, [userId]);"
        )
    return None


def _template_xss(snippet: str, _lang: str) -> Optional[str]:
    if "dangerouslySetInnerHTML" in snippet:
        out = re.sub(
            r"dangerouslySetInnerHTML=\{\{\s*__html:\s*(.+?)\s*\}\}",
            r"children={\1}",
            snippet,
        )
        return out if out != snippet else None
    if ".innerHTML" in snippet:
        return snippet.replace(".innerHTML", ".textContent")
    return None


def _template_cmdi(snippet: str, _lang: str) -> Optional[str]:
    if "exec(" in snippet and "execFile(" not in snippet:
        return snippet.replace("exec(", "execFile(")
    return None


def _template_path_traversal(snippet: str, lang: str) -> Optional[str]:
    if lang == "javascript" and "path.join" in snippet and "req." in snippet:
        return (
            "const name = path.basename(req.params.file || '');\n"
            "const safePath = path.join(BASE_DIR, name);"
        )
    if lang == "python" and "os.path.join" in snippet and "request" in snippet:
        return (
            "name = os.path.basename(request.args.get('file', ''))\n"
            "safe_path = os.path.join(BASE_DIR, name)"
        )
    return None


def _template_hardcoded_secret(snippet: str, lang: str) -> Optional[str]:
    if lang == "javascript":
        out = re.sub(r"(['\"])(password|secret|token|apikey|api_key)\1\s*:\s*['\"][^'\"]+['\"]", r"\1\2\1: process.env.SECRET_VALUE", snippet, flags=re.IGNORECASE)
        if out != snippet:
            return out
    if lang == "python":
        out = re.sub(r"(password|secret|token|api_key)\s*=\s*['\"][^'\"]+['\"]", r"\1 = os.getenv('SECRET_VALUE')", snippet, flags=re.IGNORECASE)
        if out != snippet:
            return out
    return None


def _template_cors(snippet: str, _lang: str) -> Optional[str]:
    if "Access-Control-Allow-Origin" in snippet and "*" in snippet:
        return snippet.replace("*", "https://trusted.example.com")
    if "cors(" in snippet and "origin: '*'" in snippet:
        return snippet.replace("origin: '*'", "origin: ['https://trusted.example.com']")
    return None


def apply(cwe: str, file_path: str, snippet: str) -> Optional[dict[str, str]]:
    lang = _lang_from_path(file_path)
    key = (cwe or "").upper().strip()

    transform = None
    if key == "CWE-89":
        transform = _template_sqli(snippet, lang)
    elif key == "CWE-79":
        transform = _template_xss(snippet, lang)
    elif key == "CWE-78":
        transform = _template_cmdi(snippet, lang)
    elif key == "CWE-22":
        transform = _template_path_traversal(snippet, lang)
    elif key == "CWE-798":
        transform = _template_hardcoded_secret(snippet, lang)
    elif key == "CWE-942":
        transform = _template_cors(snippet, lang)

    if not transform or transform.strip() == snippet.strip():
        return None

    return {
        "unsafe_reason": f"Deterministic template fix applied for {key}",
        "fixed_code": transform,
        "patch_safety": "review_needed",
    }
