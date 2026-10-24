"""Bring-your-own LLM: any OpenAI-compatible endpoint (OpenAI, Groq, Together, OpenRouter, vLLM,
LM Studio, a self-hosted SLM ...) used instead of local Ollama.

Config comes from env (CYPHEX_LLM_BASE_URL / CYPHEX_LLM_API_KEY / CYPHEX_LLM_MODEL) or the file
the /llm command writes (~/.cyphex/llm.json, mode 0600). With neither, active() is False and every
caller keeps using local Ollama exactly as before. Standard library only.
"""
import asyncio
import json
import os
import pathlib
import time
import urllib.error
import urllib.request
from urllib.parse import urlparse


class ProviderError(Exception):
    """A readable provider failure. Never contains the API key."""


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):
        return None  # a redirect could forward the Authorization header to another host


_opener = urllib.request.build_opener(_NoRedirect)


def _store() -> pathlib.Path:
    return pathlib.Path(os.environ.get("CYPHEX_LLM_FILE") or pathlib.Path.home() / ".cyphex" / "llm.json")


def load() -> dict:
    """{"base_url", "api_key", "model"}; env values override the saved file. Missing keys are absent."""
    try:
        cfg = json.loads(_store().read_text())
    except Exception:
        cfg = {}
    if not isinstance(cfg, dict):
        cfg = {}
    env = {"base_url": os.environ.get("CYPHEX_LLM_BASE_URL"),
           "api_key": os.environ.get("CYPHEX_LLM_API_KEY"),
           "model": os.environ.get("CYPHEX_LLM_MODEL")}
    cfg.update({k: v for k, v in env.items() if v})
    if os.environ.get("CYPHEX_LLM_EXTRA_MODELS"):
        cfg["extra_models"] = [m.strip() for m in os.environ["CYPHEX_LLM_EXTRA_MODELS"].split(",") if m.strip()]
    return cfg


def all_models(cfg: dict | None = None) -> list[str]:
    """Primary model first, then optional extra models (a second opinion for council review)."""
    cfg = cfg or load()
    extra = cfg.get("extra_models") or []
    return list(dict.fromkeys([m for m in [cfg.get("model", ""), *extra] if m]))


def active() -> bool:
    cfg = load()
    return bool(cfg.get("base_url") and cfg.get("model"))


def normalize(url: str) -> str:
    """Accept what people paste: .../v1, .../v1/, .../v1/chat/completions."""
    url = url.strip().rstrip("/")
    for suffix in ("/chat/completions", "/models"):
        if url.endswith(suffix):
            url = url[: -len(suffix)]
    return url


def validate_url(url: str) -> str:
    """"" when fine, else a readable reason. The key travels in every request, so https only
    (plain http is allowed for localhost, e.g. a local vLLM / LM Studio)."""
    u = urlparse(url)
    if u.scheme == "https" and u.netloc:
        return ""
    if u.scheme == "http" and u.hostname in ("localhost", "127.0.0.1", "::1"):
        return ""
    return "Use an https:// URL (http:// is only allowed for localhost)."


def mask(key: str) -> str:
    return f"…{key[-4:]}" if len(key) > 8 else ("set" if key else "none")


def label(cfg: dict | None = None) -> str:
    cfg = cfg or load()
    return f"{cfg.get('model', '?')} via {urlparse(cfg.get('base_url', '')).netloc or '?'}"


def save(cfg: dict) -> None:
    path = _store()
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    path.write_text(json.dumps({k: cfg[k] for k in ("base_url", "api_key", "model", "extra_models") if cfg.get(k)}))
    path.chmod(0o600)  # holds the API key


def clear() -> bool:
    try:
        _store().unlink()
        return True
    except OSError:
        return False


def _request(cfg: dict, path: str, body: dict | None = None, timeout: float = 60) -> dict:
    headers = {"Content-Type": "application/json"}
    if cfg.get("api_key"):
        headers["Authorization"] = f"Bearer {cfg['api_key']}"
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(cfg["base_url"].rstrip("/") + path, data, headers,
                                 method="POST" if body is not None else "GET")
    try:
        with _opener.open(req, timeout=timeout) as r:
            return json.loads(r.read().decode(errors="replace"))
    except urllib.error.HTTPError as e:
        detail = e.read().decode(errors="replace")[:200].replace("\n", " ")
        raise ProviderError(f"HTTP {e.code}: {detail}") from None
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as e:
        raise ProviderError(f"could not reach the provider ({type(e).__name__})") from None


def chat_sync(system: str, prompt: str, temperature: float = 0.1, json_mode: bool = True,
              timeout: float = 120, cfg: dict | None = None, model: str | None = None) -> str:
    """One chat completion → the reply text. Retries rate limits / 5xx; drops JSON mode for providers
    that reject it. `model` is honoured only if it is one of the configured models; anything else
    (callers pass local-Ollama names like qwen2.5-coder:7b) falls back to the primary model."""
    cfg = cfg or load()
    use = model if model in all_models(cfg) else cfg["model"]
    body = {"model": use, "temperature": temperature,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": prompt}]}
    if json_mode:
        body["response_format"] = {"type": "json_object"}
    last = None
    for attempt in range(3):
        try:
            data = _request(cfg, "/chat/completions", body, timeout)
            break
        except ProviderError as e:
            last = e
            msg = str(e)
            if "response_format" in body and msg.startswith(("HTTP 400", "HTTP 422")):
                body.pop("response_format")  # provider without JSON mode: rely on the prompt
            elif msg.startswith(("HTTP 429", "HTTP 5")) or "could not reach" in msg:
                time.sleep(2 ** attempt)
            else:
                raise
    else:
        raise last
    try:
        return data["choices"][0]["message"].get("content") or ""
    except (KeyError, IndexError, TypeError, AttributeError):
        raise ProviderError("unexpected response shape from the provider") from None


async def chat(system: str, prompt: str, temperature: float = 0.1, json_mode: bool = True,
               timeout: float = 120, model: str | None = None) -> str:
    return await asyncio.to_thread(chat_sync, system, prompt, temperature, json_mode, timeout, None, model)


def list_models(cfg: dict) -> list[str]:
    data = _request(cfg, "/models", timeout=20)
    return sorted(m["id"] for m in data.get("data", []) if isinstance(m, dict) and m.get("id"))


def check(base_url: str, api_key: str, model: str = "") -> dict:
    """Try the connection the way a scan will use it. Returns
    {"ok", "base_url", "models", "model", "reply"} or {"ok": False, "error"}; tries <url> then
    <url>/v1 for bare hosts."""
    base_url = normalize(base_url)
    problem = validate_url(base_url)
    if problem:
        return {"ok": False, "error": problem}
    last_err = "no response"
    for candidate in dict.fromkeys([base_url, base_url + "/v1"]):
        cfg = {"base_url": candidate, "api_key": api_key}
        try:
            models = list_models(cfg)
        except ProviderError as e:
            last_err = str(e)
            if last_err.startswith(("HTTP 401", "HTTP 403")):
                return {"ok": False, "error": f"The provider rejected the API key ({last_err[:8]})."}
            if last_err.startswith("HTTP 404"):
                continue  # maybe the host needs /v1
            models = []  # some providers have no /models; the chat test below decides
        chosen = model or (models[0] if models else "")
        if not chosen:
            last_err = "Could not list models; pass the model name explicitly."
            continue
        cfg["model"] = chosen
        try:
            reply = chat_sync("Reply with the single word: ok", "ping", json_mode=False, timeout=60, cfg=cfg)
        except ProviderError as e:
            last_err = str(e)
            if last_err.startswith(("HTTP 401", "HTTP 403")):
                return {"ok": False, "error": f"The provider rejected the API key ({last_err[:8]})."}
            continue
        return {"ok": True, "base_url": candidate, "models": models, "model": chosen, "reply": reply.strip()[:40]}
    return {"ok": False, "error": last_err}
