"""cvs_shell's pure-Python curl emulator: the -k/--insecure flag must actually control TLS
verification (it was silently ignored, always verify=False), and -o/--output must not be able
to write outside the sandboxed cwd via a path-traversal payload in an LLM-supplied argument."""
import asyncio

import pytest

from backend.backend.agents.cvs_shell import execute_cvs_command


class _FakeClient:
    def __init__(self, **kw):
        self.kwargs = kw

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    def build_request(self, method, url, **kw):
        return {"method": method, "url": url}

    async def send(self, req):
        import types
        return types.SimpleNamespace(status_code=200, reason_phrase="OK", headers={},
                                      text="body", content=b"body", url=req["url"])


def _patch_client(monkeypatch, captured):
    def factory(**kw):
        captured.update(kw)
        return _FakeClient(**kw)
    monkeypatch.setattr("backend.backend.agents.cvs_shell.httpx.AsyncClient", factory)


def test_verify_defaults_true_and_insecure_flag_disables_it(monkeypatch, tmp_path):
    captured = {}
    _patch_client(monkeypatch, captured)
    asyncio.run(execute_cvs_command("curl https://example.com", str(tmp_path), 5))
    assert captured["verify"] is True

    captured.clear()
    asyncio.run(execute_cvs_command("curl -k https://example.com", str(tmp_path), 5))
    assert captured["verify"] is False


def test_output_path_traversal_is_rejected(monkeypatch, tmp_path):
    _patch_client(monkeypatch, {})
    result = asyncio.run(execute_cvs_command(
        f"curl https://example.com -o ../../etc/cron.d/evil", str(tmp_path), 5))
    assert result["exit_code"] == 23
    assert not (tmp_path.parent.parent / "etc" / "cron.d" / "evil").exists()


def test_output_inside_cwd_still_works(monkeypatch, tmp_path):
    _patch_client(monkeypatch, {})
    result = asyncio.run(execute_cvs_command(
        "curl https://example.com -o out.txt", str(tmp_path), 5))
    assert result["exit_code"] == 0
    assert (tmp_path / "out.txt").read_text() == "body"
