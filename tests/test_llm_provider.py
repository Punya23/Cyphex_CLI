"""Bring-your-own-LLM provider: config precedence, URL safety, connection check and chat against a
fake OpenAI-compatible server on localhost. No real provider, no key, no network."""
import contextlib
import json
import os
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from backend import llm_provider as p

KEY = "sk-test-1234567890"


@contextlib.contextmanager
def fake_provider(*, key=KEY, reject_json_mode=False, redirect=False, prefix="/v1"):
    """OpenAI-compatible stub. Records every request in .calls."""
    calls = []

    class H(BaseHTTPRequestHandler):
        def _auth_ok(self):
            return self.headers.get("Authorization") == f"Bearer {key}"

        def _send(self, code, body):
            data = json.dumps(body).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            calls.append(("GET", self.path, dict(self.headers)))
            if not self._auth_ok():
                return self._send(401, {"error": "bad key"})
            if self.path == f"{prefix}/models":
                return self._send(200, {"data": [{"id": "my-slm"}, {"id": "other"}]})
            self._send(404, {"error": "nope"})

        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            calls.append(("POST", self.path, body))
            if redirect:
                self.send_response(302)
                self.send_header("Location", "http://127.0.0.1:1/steal")
                self.end_headers()
                return
            if not self._auth_ok():
                return self._send(401, {"error": "bad key"})
            if self.path != f"{prefix}/chat/completions":
                return self._send(404, {"error": "nope"})
            if reject_json_mode and "response_format" in body:
                return self._send(400, {"error": "response_format unsupported"})
            self._send(200, {"choices": [{"message": {"content": '{"ok": true}'}}]})

        def log_message(self, *a):
            pass

    srv = HTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        yield f"http://127.0.0.1:{srv.server_port}", calls
    finally:
        srv.shutdown()


def _clean_env(monkeypatch, tmp_path):
    for k in ("CYPHEX_LLM_BASE_URL", "CYPHEX_LLM_API_KEY", "CYPHEX_LLM_MODEL"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("CYPHEX_LLM_FILE", str(tmp_path / "llm.json"))


# ── default behaviour is unchanged ───────────────────────────────────────

def test_inactive_by_default(monkeypatch, tmp_path):
    _clean_env(monkeypatch, tmp_path)
    assert p.load() == {} and not p.active()


def test_env_overrides_saved_file(monkeypatch, tmp_path):
    _clean_env(monkeypatch, tmp_path)
    p.save({"base_url": "https://a.example/v1", "api_key": "k1", "model": "m1"})
    assert p.active() and p.load()["model"] == "m1"
    monkeypatch.setenv("CYPHEX_LLM_MODEL", "m2")
    assert p.load()["model"] == "m2" and p.load()["base_url"] == "https://a.example/v1"


def test_saved_file_is_private_and_clear_removes_it(monkeypatch, tmp_path):
    _clean_env(monkeypatch, tmp_path)
    p.save({"base_url": "https://a.example/v1", "api_key": KEY, "model": "m"})
    if os.name != "nt":
        assert oct((tmp_path / "llm.json").stat().st_mode & 0o777) == "0o600"
    assert p.clear() and not p.active() and not p.clear()


# ── URL handling ─────────────────────────────────────────────────────────

def test_normalize_accepts_what_people_paste():
    assert p.normalize(" https://api.x.com/v1/chat/completions/ ") == "https://api.x.com/v1"
    assert p.normalize("https://api.x.com/v1/") == "https://api.x.com/v1"


def test_key_never_goes_over_plain_http_except_localhost():
    assert p.validate_url("https://api.x.com/v1") == ""
    assert p.validate_url("http://localhost:8000/v1") == "" and p.validate_url("http://127.0.0.1:1/v1") == ""
    assert p.validate_url("http://api.x.com/v1") and p.validate_url("ftp://x") and p.validate_url("not a url")


def test_mask_never_reveals_the_key():
    assert KEY not in p.mask(KEY) and p.mask(KEY).endswith("7890") and p.mask("") == "none"


# ── connection check ─────────────────────────────────────────────────────

def test_check_succeeds_and_finds_v1_for_a_bare_host():
    with fake_provider() as (url, calls):
        res = p.check(url, KEY)  # no /v1 given
    assert res["ok"] and res["base_url"].endswith("/v1") and res["model"] == "my-slm"
    assert res["models"] == ["my-slm", "other"]


def test_check_wrong_key_is_reported_without_leaking_it():
    with fake_provider() as (url, _):
        res = p.check(url + "/v1", "sk-wrong-000000000")
    assert not res["ok"] and "rejected the API key" in res["error"]
    assert "sk-wrong" not in res["error"]


def test_check_refuses_insecure_remote_url():
    assert not p.check("http://api.x.com/v1", KEY)["ok"]


# ── chat ─────────────────────────────────────────────────────────────────

def test_chat_sends_key_model_and_json_mode_and_returns_text():
    with fake_provider() as (url, calls):
        cfg = {"base_url": url + "/v1", "api_key": KEY, "model": "my-slm"}
        text = p.chat_sync("sys", "hello", cfg=cfg)
    assert text == '{"ok": true}'
    _, path, body = calls[-1]
    assert path == "/v1/chat/completions" and body["model"] == "my-slm"
    assert body["response_format"] == {"type": "json_object"}
    assert body["messages"][0] == {"role": "system", "content": "sys"}


def test_chat_retries_without_json_mode_when_provider_rejects_it():
    with fake_provider(reject_json_mode=True) as (url, calls):
        cfg = {"base_url": url + "/v1", "api_key": KEY, "model": "my-slm"}
        assert p.chat_sync("s", "p", cfg=cfg) == '{"ok": true}'
    assert "response_format" not in calls[-1][2] and len(calls) == 2


def test_chat_does_not_follow_redirects_with_the_key():
    with fake_provider(redirect=True) as (url, _):
        with pytest.raises(p.ProviderError) as e:
            p.chat_sync("s", "p", cfg={"base_url": url + "/v1", "api_key": KEY, "model": "m"})
    assert KEY not in str(e.value)


@pytest.mark.asyncio
async def test_async_chat_uses_saved_config(monkeypatch, tmp_path):
    _clean_env(monkeypatch, tmp_path)
    with fake_provider() as (url, _):
        p.save({"base_url": url + "/v1", "api_key": KEY, "model": "my-slm"})
        assert await p.chat("s", "p") == '{"ok": true}'


# ── extra models (a second opinion for council review) ───────────────────

def test_extra_models_are_used_only_when_configured_and_requested():
    with fake_provider() as (url, calls):
        cfg = {"base_url": url + "/v1", "api_key": KEY, "model": "big", "extra_models": ["reviewer"]}
        assert p.all_models(cfg) == ["big", "reviewer"]
        p.chat_sync("s", "p", cfg=cfg, model="reviewer")
        assert calls[-1][2]["model"] == "reviewer"
        p.chat_sync("s", "p", cfg=cfg, model="qwen2.5-coder:7b")  # a local-Ollama name: ignored
        assert calls[-1][2]["model"] == "big"


def test_extra_models_come_from_env_and_the_saved_file(monkeypatch, tmp_path):
    _clean_env(monkeypatch, tmp_path)
    p.save({"base_url": "https://a.example/v1", "model": "m", "extra_models": ["x", "y"]})
    assert p.all_models() == ["m", "x", "y"]
    monkeypatch.setenv("CYPHEX_LLM_EXTRA_MODELS", "z")
    assert p.all_models() == ["m", "z"]
