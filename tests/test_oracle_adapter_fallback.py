"""CyphexReasoner.generate()'s direct-Ollama fallback.

Before this fix, generate() returned an EMPTY response whenever Oracle's
optional agent-reasoning package wasn't installed (self.interceptor is
None, the common case) or its call failed — in under a millisecond, no
network call at all. Every DeepAgent planner call then saw an empty
response, treated it as "LLM unavailable", and returned 0 hypotheses: a
scan looked complete in seconds without testing anything. These tests
pin the fallback that actually calls Ollama now. All httpx calls mocked.
"""
from unittest.mock import MagicMock, patch

from backend.reasoning.oracle_adapter import CyphexReasoner


def _mock_response(status=200, body=None):
    r = MagicMock()
    r.status_code = status
    r.json.return_value = body or {}
    if status >= 400:
        import httpx
        r.raise_for_status.side_effect = httpx.HTTPStatusError(
            "error", request=MagicMock(), response=r)
    else:
        r.raise_for_status.return_value = None
    return r


def _client_returning(response):
    client = MagicMock()
    client.__enter__.return_value = client
    client.__exit__.return_value = False
    client.post.return_value = response
    return client


def test_no_interceptor_falls_back_to_direct_ollama_not_empty():
    reasoner = CyphexReasoner()
    assert reasoner.interceptor is None  # agent-reasoning not installed in CI

    client = _client_returning(_mock_response(200, {"response": "real model output"}))
    with patch("backend.reasoning.oracle_adapter.httpx.Client", return_value=client):
        result = reasoner.generate(model="qwen2.5-coder:7b", prompt="plan an attack",
                                   task_type="vuln_analysis")

    assert result.response == "real model output"
    assert result.reasoning_available is False
    assert result.strategy == "direct"
    client.post.assert_called_once()
    url, kwargs = client.post.call_args.args[0], client.post.call_args.kwargs
    assert url == "http://localhost:11434/api/generate"
    assert kwargs["json"]["model"] == "qwen2.5-coder:7b"
    assert kwargs["json"]["stream"] is False


def test_direct_ollama_sends_a_bounded_context_not_the_models_own_max():
    """Real incident: with no `options`, Ollama loaded llama3.1:8b at its
    own max context (131072), a 23GB footprint that no longer fit in
    unified memory/VRAM — forcing a 52%/48% CPU/GPU split and making every
    single call pathologically slow regardless of free RAM. num_ctx must
    be sent, and small enough that this can't recur."""
    reasoner = CyphexReasoner()
    client = _client_returning(_mock_response(200, {"response": "ok"}))
    with patch("backend.reasoning.oracle_adapter.httpx.Client", return_value=client):
        reasoner.generate(model="llama3.1:8b", prompt="plan an attack")
    options = client.post.call_args.kwargs["json"]["options"]
    assert 0 < options["num_ctx"] <= 8192


def test_direct_ollama_uses_the_callers_timeout_not_a_hardcoded_one():
    """Real incident: generate()'s own httpx timeout was a fixed 120s,
    completely decoupled from oracle_attack.py's per-role budget (raised to
    150-240s+) — so raising that outer budget never had any real effect.
    The caller's timeout must actually reach the httpx.Client."""
    reasoner = CyphexReasoner()
    with patch("backend.reasoning.oracle_adapter.httpx.Client") as mock_client_cls:
        mock_client_cls.return_value = _client_returning(_mock_response(200, {"response": "ok"}))
        reasoner.generate(model="m", prompt="x", timeout=390.0)
    assert mock_client_cls.call_args.kwargs["timeout"] == 390.0


def test_direct_ollama_sends_system_and_prompt_combined():
    reasoner = CyphexReasoner()
    client = _client_returning(_mock_response(200, {"response": "ok"}))
    with patch("backend.reasoning.oracle_adapter.httpx.Client", return_value=client):
        reasoner.generate(model="m", prompt="do X", system="You are a planner")
    sent_prompt = client.post.call_args.kwargs["json"]["prompt"]
    assert "You are a planner" in sent_prompt
    assert "do X" in sent_prompt


def test_direct_ollama_degrades_to_empty_on_http_error_never_raises():
    reasoner = CyphexReasoner()
    client = _client_returning(_mock_response(404))
    with patch("backend.reasoning.oracle_adapter.httpx.Client", return_value=client):
        result = reasoner.generate(model="missing-model", prompt="x")
    assert result.response == ""
    assert result.reasoning_available is False


def test_direct_ollama_degrades_to_empty_when_ollama_unreachable():
    reasoner = CyphexReasoner()
    with patch("backend.reasoning.oracle_adapter.httpx.Client", side_effect=OSError("connection refused")):
        result = reasoner.generate(model="m", prompt="x")
    assert result.response == ""


def test_interceptor_present_never_touches_direct_ollama():
    reasoner = CyphexReasoner()
    reasoner.interceptor = MagicMock()
    reasoner.interceptor.generate.return_value = {"response": "enhanced output"}

    with patch.object(reasoner, "_direct_ollama") as mock_direct:
        result = reasoner.generate(model="qwen2.5-coder:7b", prompt="plan")

    mock_direct.assert_not_called()
    assert result.response == "enhanced output"
    assert result.reasoning_available is True


def test_interceptor_failure_falls_back_to_direct_ollama():
    reasoner = CyphexReasoner()
    reasoner.interceptor = MagicMock()
    reasoner.interceptor.generate.side_effect = RuntimeError("interceptor exploded")

    with patch.object(reasoner, "_direct_ollama", return_value="fallback output") as mock_direct:
        result = reasoner.generate(model="qwen2.5-coder:7b", prompt="plan")

    mock_direct.assert_called_once()
    assert result.response == "fallback output"
    assert result.reasoning_available is False
