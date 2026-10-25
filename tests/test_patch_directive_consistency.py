"""A hypothesis's CWE tag comes from the PLANNER LLM's free-text output, not
deterministic code, and can be inconsistent with the finding's own name — a
live scan confirmed this: "Internal IP Leakage", "Internal Service
Discovery", and "HTTP Request Smuggling" were all tagged CWE-89 (SQL
injection). _build_patch_prompt used to trust that tag blindly and hand the
generator the SQLi fix directive ("replace template literals with
parameterized queries") for findings with no SQL in them at all —
guaranteeing a no-op patch (the generator had nothing matching to change),
not just a wrong one. _directive_for() only trusts a CWE-specific directive
when the finding's own name is consistent with it.
"""
from backend.council.patch_council import _directive_for, _build_patch_prompt, CWE_DIRECTIVES, _GENERIC_DIRECTIVE


def test_matching_name_gets_the_cwe_specific_directive():
    d = _directive_for("SQL Injection (String Concatenation)", "CWE-89")
    assert d == CWE_DIRECTIVES["CWE-89"]


def test_mismatched_name_falls_back_to_generic_not_the_wrong_directive():
    """The real live bug: a non-SQL finding mistagged CWE-89 must NOT get
    SQLi-specific instructions it can't act on."""
    d = _directive_for("Internal IP Leakage", "CWE-89")
    assert d == _GENERIC_DIRECTIVE
    assert d != CWE_DIRECTIVES["CWE-89"]


def test_http_request_smuggling_mistagged_cwe89_falls_back():
    d = _directive_for("HTTP Request Smuggling (CWE-89)", "CWE-89")
    assert d == _GENERIC_DIRECTIVE


def test_internal_service_discovery_mistagged_cwe89_falls_back():
    d = _directive_for("Internal Service Discovery", "CWE-89")
    assert d == _GENERIC_DIRECTIVE


def test_ssrf_name_with_correct_cwe_gets_ssrf_directive():
    d = _directive_for("SSRF via Internal IP Leakage", "CWE-918")
    assert d == CWE_DIRECTIVES["CWE-918"]


def test_unknown_cwe_always_falls_back_to_generic():
    assert _directive_for("Whatever", "CWE-9999") == _GENERIC_DIRECTIVE


def test_cwe_with_no_keyword_list_still_trusts_the_tag():
    """CWEs not in _CWE_NAME_KEYWORDS (e.g. CWE-798) keep the old
    trust-the-tag behavior — only the confirmed-mismatching CWEs changed."""
    d = _directive_for("Hardcoded Secret in Config", "CWE-798")
    assert d == CWE_DIRECTIVES["CWE-798"]


def test_build_patch_prompt_uses_the_consistency_checked_directive():
    prompt = _build_patch_prompt({
        "vuln_name": "Internal IP Leakage",
        "cwe": "CWE-89",
        "file_path": "src/routes/products.js",
        "vulnerable_code": "res.json({ ip: req.ip });",
    })
    assert "parameterized queries" not in prompt  # the wrong, SQLi-specific directive
    assert _GENERIC_DIRECTIVE in prompt
