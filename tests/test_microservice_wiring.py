"""Regression tests for the microservice wiring fixes: shared attack triple across services,
whole-word service matching, f-string / env-var call detection, personal-account repo listing,
and a Docker timeout marking one service failed instead of aborting the deploy.
No Docker, no network, no LLM."""
import subprocess
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.services.github_discovery import list_org_repos
from backend.services.multi_deploy import deploy_service_graph
from backend.services.service_discovery import _resolve_target, discover_outbound_edges
from backend.services.service_graph import ServiceGraph, ServiceNode
from cli_engine import CyphexEngine


# ── whole-word service matching ──────────────────────────────────────────

def test_resolve_target_matches_whole_words_only():
    names = ["notification-service"]
    assert _resolve_target("http://notification-service:4002/x", names) == "notification-service"
    assert _resolve_target("NOTIFICATION_SERVICE_URL", names) == "notification-service"
    assert _resolve_target("process.env.NotificationServiceUrl", names) == "notification-service"  # camelCase
    assert _resolve_target("http://author-api:3000/x", ["auth"]) == ""  # "auth" is not "author"


# ── outbound-call detection ──────────────────────────────────────────────

def test_outbound_detects_fstring_and_env_var_calls(tmp_path):
    (tmp_path / "app.py").write_text(
        'requests.get(f"http://notification-service:4002/api/{uid}")\n'
        'requests.get(os.environ["INVENTORY_SERVICE_URL"])\n')
    (tmp_path / "app.js").write_text('fetch(process.env.PAYMENT_SERVICE_URL + "/charge")\n')
    hints = [e.target_hint for e in discover_outbound_edges("orders", str(tmp_path))]
    assert any("notification-service:4002" in h for h in hints)
    assert any("INVENTORY_SERVICE_URL" in h for h in hints)
    assert any("process.env.PAYMENT_SERVICE_URL" in h for h in hints)


# ── personal accounts ────────────────────────────────────────────────────

def _resp(status, body):
    r = MagicMock()
    r.status_code = status
    r.json.return_value = body
    return r


@pytest.mark.asyncio
async def test_list_org_repos_falls_back_to_users_endpoint_for_a_personal_account():
    client = AsyncMock()
    client.get = AsyncMock(side_effect=[
        _resp(404, {}), _resp(200, [{"name": "svc", "clone_url": "https://github.com/me/svc.git"}])])
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)
    with patch("backend.services.github_discovery.httpx.AsyncClient", return_value=client):
        repos = await list_org_repos("me", "tok")
    assert repos == [{"name": "svc", "clone_url": "https://github.com/me/svc.git"}]
    assert "/orgs/me/repos" in client.get.call_args_list[0].args[0]
    assert "/users/me/repos" in client.get.call_args_list[1].args[0]


# ── a Docker timeout must not abort the deploy or leak containers ────────

@pytest.mark.asyncio
async def test_timed_out_build_is_reported_failed_and_container_is_tracked_for_teardown(tmp_path):
    graph = ServiceGraph(auto_generated=True)
    for name in ("a", "b"):
        (tmp_path / name).mkdir()
        (tmp_path / name / "package.json").write_text("{}")
        graph.add_node(ServiceNode(name=name, path=name, base_url="http://localhost:1"))

    def run(cmd, **kwargs):
        if cmd[:2] == ["docker", "build"]:
            raise subprocess.TimeoutExpired(cmd, 180)
        ok = MagicMock()
        ok.returncode, ok.stdout, ok.stderr = 0, "", ""
        return ok

    with patch("backend.services.multi_deploy.docker_available", return_value=True), \
         patch("backend.services.multi_deploy.subprocess.run", side_effect=run), \
         patch("backend.services.multi_deploy._find_free_port", side_effect=[9301, 9302]), \
         patch("backend.services.multi_deploy._check_up", new=AsyncMock(return_value=True)), \
         patch("backend.services.multi_deploy.asyncio.sleep", new=AsyncMock()):
        result = await deploy_service_graph(str(tmp_path), graph, "scan1")  # must not raise

    assert sorted(result["failed"]) == ["a", "b"] and result["deployed"] == []
    assert len(result["containers"]) == 2  # teardown_service_graph can still remove them


# ── the attack triple is shared across services in a multi-service scan ──

class _Fake:
    def __init__(self, *args, **kwargs):
        pass


def _fake_attack_classes(monkeypatch):
    for path in ("backend.deepagents.attack_graph.AttackGraph",
                 "backend.deepagents.attack_surface_index.AttackSurfaceIndex",
                 "backend.deepagents.oracle_attack.AttackOracle",
                 "backend.council.council_orchestrator.CouncilOrchestrator"):
        monkeypatch.setattr(path, _Fake)


def test_attack_triple_is_reused_across_services_in_a_multi_scan(monkeypatch):
    _fake_attack_classes(monkeypatch)
    engine = CyphexEngine()
    engine._in_multi_scan = True
    first, second = engine._attack_triple(), engine._attack_triple()
    assert all(a is b for a, b in zip(first, second))
    assert engine._shared_attack_graph is first[0]


def test_single_service_scan_gets_a_fresh_triple_each_time(monkeypatch):
    _fake_attack_classes(monkeypatch)
    engine = CyphexEngine()
    first, second = engine._attack_triple(), engine._attack_triple()
    assert first[0] is not second[0]
    assert engine._shared_attack_graph is None
