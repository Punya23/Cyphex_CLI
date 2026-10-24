"""Phase 3 orchestration: CyphexEngine._multi_service_dynamic_scan() deploys
every service, runs the existing _dynamic_scan() once per live service with
ONE shared attack graph, merges their findings, and always tears down —
this is what makes a credential found on service A still known when service
B is scanned next. deploy/teardown and _dynamic_scan are mocked; no Docker,
no network calls.
"""
from unittest.mock import AsyncMock, patch

import pytest

from backend.backend.models.scan import ScanContext, Vuln
from backend.services.service_graph import ServiceGraph, ServiceNode
from cli_engine import CyphexEngine


def _engine_with_two_services():
    engine = CyphexEngine()
    engine.source_dir = "/tmp/fake-repo"
    engine.scan_id = "scantest"
    graph = ServiceGraph(auto_generated=True)
    graph.add_node(ServiceNode(name="a", path="a", base_url="http://localhost:1"))
    graph.add_node(ServiceNode(name="b", path="b", base_url="http://localhost:2"))
    engine.service_graph = graph
    return engine


@pytest.mark.asyncio
async def test_merges_findings_from_every_service_and_resets_shared_state():
    engine = _engine_with_two_services()
    deploy_result = {"network": "net1", "containers": ["c1", "c2"],
                      "deployed": ["a", "b"], "failed": []}

    async def fake_dynamic_scan(target_url, use_deepagents=False):
        ctx = ScanContext(target_url=target_url)
        ctx.confirmed_vulns.append(Vuln(name=f"finding-for-{target_url}", severity="Low"))
        # A real _dynamic_scan constructs/reuses attack_graph via
        # self._shared_attack_graph — simulate it getting set on first call.
        if engine._shared_attack_graph is None:
            engine._shared_attack_graph = "SENTINEL_SHARED_GRAPH"
        return ctx

    with patch("backend.services.multi_deploy.deploy_service_graph",
               new=AsyncMock(return_value=deploy_result)), \
         patch("backend.services.multi_deploy.teardown_service_graph") as mock_teardown, \
         patch.object(engine, "_dynamic_scan", new=AsyncMock(side_effect=fake_dynamic_scan)) as mock_scan:
        result = await engine._multi_service_dynamic_scan(use_deepagents=True)

    assert result is not None
    assert len(result.confirmed_vulns) == 2
    assert {v.name for v in result.confirmed_vulns} == {
        "finding-for-http://localhost:1", "finding-for-http://localhost:2",
    }
    assert mock_scan.call_count == 2
    mock_teardown.assert_called_once_with(deploy_result)
    # Reset after the loop — a later single-service scan in the same process
    # must not accidentally inherit this run's attack graph.
    assert engine._shared_attack_graph is None
    assert engine._shared_asi is None
    assert engine._shared_oracle is None


@pytest.mark.asyncio
async def test_returns_none_and_still_tears_down_when_nothing_deployed():
    engine = _engine_with_two_services()
    deploy_result = {"network": "net1", "containers": ["c1", "c2"],
                      "deployed": [], "failed": ["a", "b"]}

    with patch("backend.services.multi_deploy.deploy_service_graph",
               new=AsyncMock(return_value=deploy_result)), \
         patch("backend.services.multi_deploy.teardown_service_graph") as mock_teardown, \
         patch.object(engine, "_dynamic_scan", new=AsyncMock()) as mock_scan:
        result = await engine._multi_service_dynamic_scan(use_deepagents=True)

    assert result is None
    mock_scan.assert_not_called()
    mock_teardown.assert_called_once_with(deploy_result)


@pytest.mark.asyncio
async def test_returns_none_without_teardown_when_docker_unavailable():
    engine = _engine_with_two_services()
    deploy_result = {"network": "", "containers": [], "deployed": [], "failed": ["a", "b"],
                      "error": "Docker not available"}

    with patch("backend.services.multi_deploy.deploy_service_graph",
               new=AsyncMock(return_value=deploy_result)), \
         patch("backend.services.multi_deploy.teardown_service_graph") as mock_teardown, \
         patch.object(engine, "_dynamic_scan", new=AsyncMock()) as mock_scan:
        result = await engine._multi_service_dynamic_scan(use_deepagents=True)

    assert result is None
    mock_scan.assert_not_called()
    mock_teardown.assert_not_called()


@pytest.mark.asyncio
async def test_still_tears_down_if_a_per_service_scan_raises():
    engine = _engine_with_two_services()
    deploy_result = {"network": "net1", "containers": ["c1", "c2"],
                      "deployed": ["a", "b"], "failed": []}

    with patch("backend.services.multi_deploy.deploy_service_graph",
               new=AsyncMock(return_value=deploy_result)), \
         patch("backend.services.multi_deploy.teardown_service_graph") as mock_teardown, \
         patch.object(engine, "_dynamic_scan", new=AsyncMock(side_effect=RuntimeError("boom"))):
        with pytest.raises(RuntimeError):
            await engine._multi_service_dynamic_scan(use_deepagents=True)

    mock_teardown.assert_called_once_with(deploy_result)
    assert engine._shared_attack_graph is None
