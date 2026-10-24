"""Organization-wide microservice discovery: given one GitHub repo, find its
sibling microservices elsewhere in the org (outbound call hints matched
against repo names, inbound code search for who calls it back) and assemble
them into one local workdir shaped for the existing Phase 1 pipeline.

All httpx/subprocess calls are mocked — no real GitHub API, no real git.
"""
import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.services.github_discovery import (
    assemble_workspace,
    clear_saved_token,
    discover_and_assemble_org,
    find_linked_repos,
    list_org_repos,
    load_saved_token,
    repo_owner_and_name,
    resolve_github_token,
    save_token,
    search_org_code_for_term,
)


@pytest.fixture(autouse=True)
def _isolated_token_file(tmp_path, monkeypatch):
    """Every test in this module gets its own token file — never the real
    ~/.cyphex/github_token, so a run here can't read a developer's actual
    token or leave one behind."""
    monkeypatch.setenv("CYPHEX_GITHUB_TOKEN_FILE", str(tmp_path / "github_token"))


def _http_response(status_code=200, json_data=None):
    r = MagicMock()
    r.status_code = status_code
    r.json.return_value = json_data or {}
    return r


def _ok_clone(returncode=0):
    r = MagicMock()
    r.returncode = returncode
    r.stderr = ""
    return r


# ── resolve_github_token ─────────────────────────────────────────────────

def test_resolve_github_token_prefers_env_var_without_calling_gh(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "env-token")
    with patch("backend.services.github_discovery.subprocess.run") as mock_run:
        assert resolve_github_token() == "env-token"
    mock_run.assert_not_called()


def test_resolve_github_token_falls_back_to_gh_auth_token(monkeypatch):
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    gh_result = MagicMock(returncode=0, stdout="gh-token-123\n")
    with patch("backend.services.github_discovery.subprocess.run", return_value=gh_result) as mock_run:
        assert resolve_github_token() == "gh-token-123"
    mock_run.assert_called_once_with(["gh", "auth", "token"], capture_output=True,
                                      text=True, timeout=10)


def test_resolve_github_token_empty_when_gh_not_logged_in(monkeypatch):
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    gh_result = MagicMock(returncode=1, stdout="")
    with patch("backend.services.github_discovery.subprocess.run", return_value=gh_result):
        assert resolve_github_token() == ""


def test_resolve_github_token_empty_when_gh_not_installed(monkeypatch):
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    with patch("backend.services.github_discovery.subprocess.run", side_effect=FileNotFoundError):
        assert resolve_github_token() == ""


# ── save_token / load_saved_token / clear_saved_token ───────────────────

def test_save_and_load_token_round_trip():
    assert load_saved_token() == ""
    save_token("  pasted-token  ")  # whitespace from a copy-paste, stripped
    assert load_saved_token() == "pasted-token"


def test_clear_saved_token_reports_whether_anything_was_removed():
    assert clear_saved_token() is False
    save_token("tok")
    assert clear_saved_token() is True
    assert load_saved_token() == ""


@pytest.mark.skipif(os.name == "nt", reason="chmod bits are POSIX-only; Windows has no 0o600 equivalent")
def test_save_token_sets_restrictive_permissions():
    import stat
    save_token("secret-pat")
    path = os.environ["CYPHEX_GITHUB_TOKEN_FILE"]
    mode = stat.S_IMODE(os.stat(path).st_mode)
    assert mode == 0o600


# ── resolve_github_token precedence (env > saved file > gh) ──────────────

def test_resolve_prefers_env_over_saved_token(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "env-token")
    save_token("saved-token")
    assert resolve_github_token() == "env-token"


def test_resolve_prefers_saved_token_over_gh(monkeypatch):
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    save_token("saved-token")
    with patch("backend.services.github_discovery.subprocess.run") as mock_run:
        assert resolve_github_token() == "saved-token"
    mock_run.assert_not_called()


def test_resolve_falls_back_to_gh_when_nothing_saved(monkeypatch):
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    gh_result = MagicMock(returncode=0, stdout="gh-token\n")
    with patch("backend.services.github_discovery.subprocess.run", return_value=gh_result):
        assert resolve_github_token() == "gh-token"


# ── repo_owner_and_name ──────────────────────────────────────────────────

@pytest.mark.parametrize("url,expected", [
    ("https://github.com/acme/whatsapp-broadcast.git", ("acme", "whatsapp-broadcast")),
    ("https://github.com/acme/whatsapp-broadcast", ("acme", "whatsapp-broadcast")),
    ("https://github.com/acme/whatsapp-broadcast/", ("acme", "whatsapp-broadcast")),
    ("https://gitlab.com/acme/foo", None),
    ("not-a-url", None),
])
def test_repo_owner_and_name(url, expected):
    assert repo_owner_and_name(url) == expected


# ── list_org_repos ───────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_org_repos_paginates_until_a_short_page():
    page1 = [{"name": f"svc-{i}", "clone_url": f"https://github.com/acme/svc-{i}.git"}
             for i in range(100)]
    page2 = [{"name": "svc-100", "clone_url": "https://github.com/acme/svc-100.git"}]

    client = AsyncMock()
    client.get = AsyncMock(side_effect=[_http_response(200, page1), _http_response(200, page2)])
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)

    with patch("backend.services.github_discovery.httpx.AsyncClient", return_value=client):
        repos = await list_org_repos("acme", "tok")

    assert len(repos) == 101
    assert repos[0]["name"] == "svc-0"
    assert client.get.call_count == 2


@pytest.mark.asyncio
async def test_list_org_repos_empty_on_non_200():
    client = AsyncMock()
    client.get = AsyncMock(return_value=_http_response(404, {}))
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)
    with patch("backend.services.github_discovery.httpx.AsyncClient", return_value=client):
        assert await list_org_repos("nonexistent-org", "") == []


# ── search_org_code_for_term ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_search_org_code_requires_a_token():
    assert await search_org_code_for_term("acme", "whatsapp-broadcast", "") == []


@pytest.mark.asyncio
async def test_search_org_code_returns_repo_names():
    data = {"items": [
        {"repository": {"name": "notification-service"}},
        {"repository": {"name": "notification-service"}},  # dedup
        {"repository": {"name": "order-service"}},
    ]}
    client = AsyncMock()
    client.get = AsyncMock(return_value=_http_response(200, data))
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)
    with patch("backend.services.github_discovery.httpx.AsyncClient", return_value=client):
        names = await search_org_code_for_term("acme", "whatsapp-broadcast", "tok")
    assert names == ["notification-service", "order-service"]


# ── find_linked_repos ────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_find_linked_repos_catches_outbound_and_inbound(tmp_path):
    (tmp_path / "index.js").write_text(
        "fetch(`${process.env.NOTIFICATION_SERVICE_URL}/api/notify`);\n"
    )
    org_repos = [
        {"name": "notification-service", "clone_url": "https://github.com/acme/notification-service.git"},
        {"name": "order-service", "clone_url": "https://github.com/acme/order-service.git"},
        {"name": "unrelated-service", "clone_url": "https://github.com/acme/unrelated-service.git"},
    ]
    with patch("backend.services.github_discovery.list_org_repos",
               new=AsyncMock(return_value=org_repos)), \
         patch("backend.services.github_discovery.search_org_code_for_term",
               new=AsyncMock(return_value=["order-service"])):
        linked = await find_linked_repos(str(tmp_path), "whatsapp-broadcast", "acme", "tok")

    names = {r["name"] for r in linked}
    assert names == {"notification-service", "order-service"}
    assert "unrelated-service" not in names


@pytest.mark.asyncio
async def test_find_linked_repos_empty_org_listing_short_circuits(tmp_path):
    (tmp_path / "x.py").write_text("x = 1\n")
    with patch("backend.services.github_discovery.list_org_repos",
               new=AsyncMock(return_value=[])):
        assert await find_linked_repos(str(tmp_path), "main", "acme", "tok") == []


# ── assemble_workspace ───────────────────────────────────────────────────

def test_assemble_workspace_clones_main_and_every_linked_repo(tmp_path):
    linked = [{"name": "notification-service", "clone_url": "https://github.com/acme/notification-service.git"}]
    with patch("backend.services.github_discovery._clone_shallow", return_value=True) as mock_clone:
        result = assemble_workspace("https://github.com/acme/whatsapp-broadcast.git",
                                     "whatsapp-broadcast", linked, str(tmp_path))
    assert result == {"cloned": ["whatsapp-broadcast", "notification-service"], "failed": []}
    assert mock_clone.call_count == 2


def test_assemble_workspace_reports_a_failed_clone_without_crashing(tmp_path):
    linked = [{"name": "notification-service", "clone_url": "https://github.com/acme/notification-service.git"}]
    with patch("backend.services.github_discovery._clone_shallow", side_effect=[True, False]):
        result = assemble_workspace("https://github.com/acme/whatsapp-broadcast.git",
                                     "whatsapp-broadcast", linked, str(tmp_path))
    assert result == {"cloned": ["whatsapp-broadcast"], "failed": ["notification-service"]}


# ── discover_and_assemble_org (top-level) ────────────────────────────────

@pytest.mark.asyncio
async def test_non_github_url_returns_none_immediately(tmp_path):
    with patch("backend.services.github_discovery._clone_shallow") as mock_clone:
        result = await discover_and_assemble_org("https://gitlab.com/acme/foo", str(tmp_path))
    assert result is None
    mock_clone.assert_not_called()


@pytest.mark.asyncio
async def test_probe_clone_failure_returns_none(tmp_path):
    with patch("backend.services.github_discovery._clone_shallow", return_value=False):
        result = await discover_and_assemble_org(
            "https://github.com/acme/whatsapp-broadcast", str(tmp_path), token="tok")
    assert result is None


@pytest.mark.asyncio
async def test_happy_path_returns_org_main_repo_and_cleans_up_probe_dir(tmp_path):
    linked = [{"name": "notification-service", "clone_url": "https://github.com/acme/notification-service.git"}]

    def fake_clone(repo_url, dest, branch=""):
        os.makedirs(dest, exist_ok=True)
        return True

    with patch("backend.services.github_discovery._clone_shallow", side_effect=fake_clone), \
         patch("backend.services.github_discovery.find_linked_repos",
               new=AsyncMock(return_value=linked)):
        result = await discover_and_assemble_org(
            "https://github.com/acme/whatsapp-broadcast", str(tmp_path), token="tok")

    assert result["org"] == "acme"
    assert result["main_repo"] == "whatsapp-broadcast"
    assert set(result["cloned"]) == {"whatsapp-broadcast", "notification-service"}
    probe_dir = str(tmp_path / ".__probe_whatsapp-broadcast")
    assert not os.path.exists(probe_dir), "probe clone must be cleaned up, not left behind"
