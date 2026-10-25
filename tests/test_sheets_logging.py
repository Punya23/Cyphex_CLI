"""BaseDeepAgent._log_hypothesis_row(): one row per tested hypothesis to
every connected Google Sheet — confirmed and not-found outcomes both log,
with a reason for the latter. No-op with nothing connected.
"""
from unittest.mock import patch

import pytest

from backend.deepagents.attack_graph import AttackGraph
from backend.deepagents.attack_surface_index import AttackSurfaceIndex
from backend.deepagents.base_deep_agent import BaseDeepAgent, HypothesisResult
from backend.deepagents.oracle_attack import HttpRequest, Hypothesis
from backend.backend.models.scan import ScanContext, Vuln


class _FakeAgent(BaseDeepAgent):
    PRIMARY_VULN_CLASS = "Test"


def _agent():
    return _FakeAgent(scan_id="s1", target_url="http://localhost:4001",
                      attack_graph=AttackGraph(), asi=AttackSurfaceIndex(), oracle=None)


def _hyp():
    req = HttpRequest(method="GET", path="/api/x", payload="' OR 1=1--", body="")
    return Hypothesis(id="h1", vuln_type="SQL Injection", cwe="CWE-89",
                      severity="High", test_request=req, reject_signal="", confirm_signal="")


def test_no_connection_builds_no_row_at_all():
    agent = _agent()
    with patch("cyphex.sheets.saved", return_value=[]), \
         patch("cyphex.sheets.log_row") as mock_log:
        agent._log_hypothesis_row(ScanContext(target_url=agent.target), _hyp(),
                                   HypothesisResult(False, reason="dead route (HTTP 404)"))
    mock_log.assert_not_called()


def test_confirmed_outcome_logs_the_vuln_fields():
    agent = _agent()
    vuln = Vuln(name="SQL Injection", cwe="CWE-89", severity="High",
               endpoint="/api/x", confirmed=True, description="Confirmed SQLi on /api/x.")
    with patch("cyphex.sheets.saved", return_value=[{"url": "u", "secret": "s"}]), \
         patch("cyphex.sheets.log_row") as mock_log:
        agent._log_hypothesis_row(ScanContext(target_url=agent.target), _hyp(),
                                   HypothesisResult(True, vuln, 92))
    row = mock_log.call_args.args[0]
    assert row["Outcome"] == "confirmed"
    assert row["Vulnerability"] == "SQL Injection"
    assert row["Endpoint"] == "/api/x"
    assert row["Payload"] == "' OR 1=1--"
    assert row["Confidence"] == 92
    assert "Confirmed SQLi" in row["Reason"]


def test_not_found_outcome_logs_the_reason():
    agent = _agent()
    with patch("cyphex.sheets.saved", return_value=[{"url": "u", "secret": "s"}]), \
         patch("cyphex.sheets.log_row") as mock_log:
        agent._log_hypothesis_row(ScanContext(target_url=agent.target), _hyp(),
                                   HypothesisResult(False, reason="dead route (HTTP 404)"))
    row = mock_log.call_args.args[0]
    assert row["Outcome"] == "not found"
    assert row["Reason"] == "dead route (HTTP 404)"
    assert row["Vulnerability"] == "SQL Injection"  # falls back to the hypothesis's own vuln_type


def test_row_has_exactly_the_sheet_columns():
    from cyphex import sheets
    agent = _agent()
    with patch("cyphex.sheets.saved", return_value=[{"url": "u", "secret": "s"}]), \
         patch("cyphex.sheets.log_row") as mock_log:
        agent._log_hypothesis_row(ScanContext(target_url=agent.target), _hyp(), HypothesisResult(False, reason="x"))
    assert set(mock_log.call_args.args[0]) == set(sheets.COLUMNS)


def test_never_raises_when_sheets_module_is_unimportable():
    agent = _agent()
    with patch("builtins.__import__", side_effect=ImportError("boom")):
        agent._log_hypothesis_row(ScanContext(target_url=agent.target), _hyp(),
                                   HypothesisResult(False, reason="x"))  # must not raise


class TestRunBanners:
    """log_run_start()/log_run_end() post a styled banner event to every
    connected sheet, separate from log_row()'s per-hypothesis rows — the
    visual run separator the Outcome column alone can't give you."""

    def test_run_start_posts_one_event_per_connection(self):
        from cyphex import sheets
        with patch.object(sheets, "saved",
                           return_value=[{"url": "u1", "secret": "s1"}, {"url": "u2", "secret": "s2"}]), \
             patch.object(sheets._pool, "submit", side_effect=lambda fn, *a, **k: fn(*a, **k)), \
             patch.object(sheets, "_post_now") as mock_post:
            sheets.log_run_start("scan_1", "https://example.com/app", "2026-01-01T00:00:00+00:00")
        assert mock_post.call_count == 2
        urls = {c.args[0] for c in mock_post.call_args_list}
        assert urls == {"u1", "u2"}
        body = mock_post.call_args_list[0].args[1]
        assert body["type"] == "run_start"
        assert body["scan_id"] == "scan_1"
        assert body["secret"] == "s1"

    def test_run_end_includes_before_after_and_patch_count(self):
        from cyphex import sheets
        with patch.object(sheets, "saved", return_value=[{"url": "u", "secret": "s"}]), \
             patch.object(sheets._pool, "submit", side_effect=lambda fn, *a, **k: fn(*a, **k)), \
             patch.object(sheets, "_post_now") as mock_post:
            sheets.log_run_end("scan_1", 17, 24, 7)
        body = mock_post.call_args.args[1]
        assert body == {
            "type": "run_end", "scan_id": "scan_1",
            "score_before": 17, "score_after": 24, "patches_applied": 7,
            "secret": "s",
        }

    def test_no_connection_posts_nothing(self):
        from cyphex import sheets
        with patch.object(sheets, "saved", return_value=[]), \
             patch.object(sheets, "_post_now") as mock_post:
            sheets.log_run_start("scan_1", "t", "ts")
            sheets.log_run_end("scan_1", 0, 0, 0)
        mock_post.assert_not_called()

    def test_apps_script_handles_run_start_and_run_end_types(self):
        """The webhook side (Apps Script) must branch on d.type for both new
        event kinds, not just 'row' — this is the actual visual-separator
        logic; a regression here would silently stop styling anything."""
        from cyphex import sheets
        script = sheets.setup_script("secret")
        assert "run_start" in script
        assert "run_end" in script
        assert "merge()" in script  # banner rows span the full row width
        assert "setBackground" in script  # header + banners are actually styled
