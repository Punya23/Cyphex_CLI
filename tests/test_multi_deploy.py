"""Phase 3 microservice VAPT: deploy every detected service on one Docker
network. All subprocess/network calls are mocked — these tests never touch
real Docker, same as the rest of this suite never calls real Ollama/Docker.
"""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.services.multi_deploy import (
    _env_var_override,
    deploy_service_graph,
    teardown_service_graph,
)
from backend.services.service_graph import ServiceEdge, ServiceGraph, ServiceNode


def _two_service_graph():
    graph = ServiceGraph(auto_generated=True)
    graph.add_node(ServiceNode(name="whatsapp-broadcast", path="whatsapp-broadcast",
                                base_url="http://localhost:9001"))
    graph.add_node(ServiceNode(name="notification-service", path="notification-service",
                                base_url="http://localhost:9002"))
    graph.edges.append(ServiceEdge(source="whatsapp-broadcast", target="notification-service",
                                    source_route="", target_hint="NOTIFICATION_SERVICE_URL",
                                    file="index.js:4"))
    return graph


def _write_service_dirs(tmp_path):
    for name in ("whatsapp-broadcast", "notification-service"):
        d = tmp_path / name
        d.mkdir()
        (d / "package.json").write_text("{}")


def _ok_completed(stdout="", stderr=""):
    r = MagicMock()
    r.returncode = 0
    r.stdout = stdout
    r.stderr = stderr
    return r


def _fail_completed(stderr="boom"):
    r = MagicMock()
    r.returncode = 1
    r.stdout = ""
    r.stderr = stderr
    return r


# ── _env_var_override ────────────────────────────────────────────────────

def test_env_var_override_resolves_alias_and_internal_port():
    graph = _two_service_graph()
    app_info = {"notification-service": {"type": "node", "entry": "node index.js", "port": 3000}}
    edge = graph.edges[0]
    result = _env_var_override(edge, graph, app_info)
    assert result == ("NOTIFICATION_SERVICE_URL", "http://notification-service:3000")


def test_env_var_override_none_for_literal_hostname_hint():
    """A literal http://notification-service:4002/x hint has no ALL_CAPS
    identifier — nothing to override, the network alias alone resolves it."""
    graph = _two_service_graph()
    edge = ServiceEdge(source="whatsapp-broadcast", target="notification-service",
                        source_route="", target_hint="http://notification-service:4002/api/notify",
                        file="x.js:1")
    assert _env_var_override(edge, graph, {}) is None


# ── deploy_service_graph ─────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_no_docker_returns_error_without_any_subprocess_call(tmp_path):
    _write_service_dirs(tmp_path)
    graph = _two_service_graph()
    with patch("backend.services.multi_deploy.docker_available", return_value=False), \
         patch("backend.services.multi_deploy.subprocess.run") as mock_run:
        result = await deploy_service_graph(str(tmp_path), graph, "scan1")
    assert result["error"] == "Docker not available"
    assert set(result["failed"]) == {"whatsapp-broadcast", "notification-service"}
    mock_run.assert_not_called()


@pytest.mark.asyncio
async def test_happy_path_sets_base_url_and_marks_deployed(tmp_path):
    _write_service_dirs(tmp_path)
    graph = _two_service_graph()

    with patch("backend.services.multi_deploy.docker_available", return_value=True), \
         patch("backend.services.multi_deploy.subprocess.run", return_value=_ok_completed()), \
         patch("backend.services.multi_deploy._find_free_port", side_effect=[9101, 9102]), \
         patch("backend.services.multi_deploy._check_up", new=AsyncMock(return_value=True)), \
         patch("backend.services.multi_deploy.asyncio.sleep", new=AsyncMock()):
        result = await deploy_service_graph(str(tmp_path), graph, "scan1")

    assert set(result["deployed"]) == {"whatsapp-broadcast", "notification-service"}
    assert result["failed"] == []
    assert graph.nodes["whatsapp-broadcast"].base_url == "http://localhost:9101"
    assert graph.nodes["notification-service"].base_url == "http://localhost:9102"
    assert len(result["containers"]) == 2
    # Dockerfiles were generated and cleaned up (package.json, no Dockerfile given).
    for name in ("whatsapp-broadcast", "notification-service"):
        assert not (tmp_path / name / "Dockerfile").exists()


@pytest.mark.asyncio
async def test_build_failure_leaves_node_unreachable_not_falsely_deployed(tmp_path):
    _write_service_dirs(tmp_path)
    graph = _two_service_graph()
    original_base_url = graph.nodes["whatsapp-broadcast"].base_url

    def run_side_effect(cmd, **kwargs):
        if cmd[:2] == ["docker", "build"]:
            return _fail_completed("build error")
        return _ok_completed()

    with patch("backend.services.multi_deploy.docker_available", return_value=True), \
         patch("backend.services.multi_deploy.subprocess.run", side_effect=run_side_effect), \
         patch("backend.services.multi_deploy._find_free_port", side_effect=[9201, 9202]), \
         patch("backend.services.multi_deploy._check_up", new=AsyncMock(return_value=True)), \
         patch("backend.services.multi_deploy.asyncio.sleep", new=AsyncMock()):
        result = await deploy_service_graph(str(tmp_path), graph, "scan1")

    assert "whatsapp-broadcast" in result["failed"]
    assert "whatsapp-broadcast" not in result["deployed"]
    # Never claim a service is live just because build was attempted.
    assert graph.nodes["whatsapp-broadcast"].base_url == original_base_url


@pytest.mark.asyncio
async def test_unreachable_after_run_is_failed_not_deployed(tmp_path):
    _write_service_dirs(tmp_path)
    graph = _two_service_graph()
    with patch("backend.services.multi_deploy.docker_available", return_value=True), \
         patch("backend.services.multi_deploy.subprocess.run", return_value=_ok_completed()), \
         patch("backend.services.multi_deploy._find_free_port", side_effect=[9301, 9302]), \
         patch("backend.services.multi_deploy._check_up", new=AsyncMock(return_value=False)), \
         patch("backend.services.multi_deploy.asyncio.sleep", new=AsyncMock()):
        result = await deploy_service_graph(str(tmp_path), graph, "scan1")

    assert result["deployed"] == []
    assert set(result["failed"]) == {"whatsapp-broadcast", "notification-service"}


# ── teardown_service_graph ───────────────────────────────────────────────

def test_teardown_removes_every_container_and_the_network():
    result = {
        "network": "cyphex-net-scan1",
        "containers": ["cyphex-svc-scan1-a", "cyphex-svc-scan1-b"],
        "deployed": ["a"], "failed": ["b"],
    }
    with patch("backend.services.multi_deploy.subprocess.run") as mock_run:
        teardown_service_graph(result)

    calls = [c.args[0] for c in mock_run.call_args_list]
    assert ["docker", "rm", "-f", "cyphex-svc-scan1-a"] in calls
    assert ["docker", "rm", "-f", "cyphex-svc-scan1-b"] in calls
    assert ["docker", "network", "rm", "cyphex-net-scan1"] in calls


def test_teardown_never_raises_when_docker_itself_errors():
    result = {"network": "net1", "containers": ["c1"], "deployed": [], "failed": ["c1"]}
    with patch("backend.services.multi_deploy.subprocess.run", side_effect=OSError("no docker")):
        teardown_service_graph(result)  # must not raise
