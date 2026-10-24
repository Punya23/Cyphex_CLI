"""Phase 2 microservice VAPT: feed the Phase 1 ServiceGraph into the live
scan so a credential/token confirmed on one service proposes (and actually
tests) a sibling service it calls.

Covers:
  - AttackGraph.update_from_finding()'s new deterministic cross_service_pivot
    chain (no LLM — same style as the existing SQLi/token/IDOR chains).
  - AttackSurfaceIndex.summarise_for_prompt()'s "Known downstream services"
    section, only when a service context is set.
  - BaseDeepAgent._probe_cross_service() actually firing the follow-up
    request and reporting Cross-Service Credential Reuse when accepted.
"""
from unittest.mock import AsyncMock, patch

import pytest

from backend.deepagents.attack_graph import AttackEdge, AttackGraph
from backend.deepagents.attack_surface_index import AttackSurfaceIndex
from backend.deepagents.base_deep_agent import BaseDeepAgent
from backend.backend.models.scan import ScanContext, Vuln
from backend.services.service_graph import ServiceEdge, ServiceGraph, ServiceNode


def _two_service_graph():
    graph = ServiceGraph(auto_generated=True)
    graph.add_node(ServiceNode(name="whatsapp-broadcast", path="whatsapp-broadcast",
                                base_url="http://localhost:4001", routes=["/api/broadcast"]))
    graph.add_node(ServiceNode(name="notification-service", path="notification-service",
                                base_url="http://localhost:4002", routes=["/api/notify"]))
    graph.edges.append(ServiceEdge(source="whatsapp-broadcast", target="notification-service",
                                    source_route="", target_hint="NOTIFICATION_SERVICE_URL",
                                    file="index.js:4"))
    return graph


# ── AttackGraph ──────────────────────────────────────────────────────────

def test_no_service_graph_set_means_no_pivot_edges():
    """Plain single-service scan: zero behaviour change."""
    ag = AttackGraph()
    ag.confirmed_tokens.append("fake.jwt.token")
    finding = Vuln(name="Sensitive Data Exposure", severity="Medium", endpoint="/api/profile")
    chains = ag.update_from_finding(finding)
    assert not any(e.action == "cross_service_pivot" for e in chains)


def test_token_plus_service_graph_proposes_pivot_to_sibling():
    ag = AttackGraph()
    ag.service_graph = _two_service_graph()
    ag.current_service = "whatsapp-broadcast"
    ag.confirmed_tokens.append("fake.jwt.token")

    finding = Vuln(name="Sensitive Data Exposure", severity="Medium", endpoint="/api/profile")
    chains = ag.update_from_finding(finding)

    pivots = [e for e in chains if e.action == "cross_service_pivot"]
    assert len(pivots) == 1
    assert pivots[0].target == "http://localhost:4002/api/notify"
    assert pivots[0].priority == "critical"


def test_pivot_edge_to_same_target_route_is_not_duplicated():
    ag = AttackGraph()
    ag.service_graph = _two_service_graph()
    ag.current_service = "whatsapp-broadcast"
    ag.confirmed_tokens.append("fake.jwt.token")

    f1 = Vuln(name="Sensitive Data Exposure", severity="Medium", endpoint="/api/profile")
    f2 = Vuln(name="Sensitive Data Exposure", severity="Medium", endpoint="/api/profile2")
    chains1 = ag.update_from_finding(f1)
    chains2 = ag.update_from_finding(f2)

    assert len([e for e in chains1 if e.action == "cross_service_pivot"]) == 1
    assert not [e for e in chains2 if e.action == "cross_service_pivot"]


def test_no_credential_yet_means_no_pivot():
    ag = AttackGraph()
    ag.service_graph = _two_service_graph()
    ag.current_service = "whatsapp-broadcast"
    # No confirmed_tokens / confirmed_creds — nothing reusable yet.
    finding = Vuln(name="Missing Security Headers", severity="Low", endpoint="/")
    chains = ag.update_from_finding(finding)
    assert not any(e.action == "cross_service_pivot" for e in chains)


# ── AttackSurfaceIndex ───────────────────────────────────────────────────

def test_prompt_has_no_downstream_section_without_service_context():
    asi = AttackSurfaceIndex()
    assert "Known downstream services" not in asi.summarise_for_prompt()


def test_prompt_lists_downstream_services_once_set():
    asi = AttackSurfaceIndex()
    asi.set_service_context(_two_service_graph(), "whatsapp-broadcast")
    summary = asi.summarise_for_prompt()
    assert "Known downstream services" in summary
    assert "notification-service" in summary
    assert "/api/notify" in summary


def test_prompt_downstream_section_absent_for_leaf_service():
    """notification-service has no outbound edges of its own — nothing to list."""
    asi = AttackSurfaceIndex()
    asi.set_service_context(_two_service_graph(), "notification-service")
    assert "Known downstream services" not in asi.summarise_for_prompt()


# ── BaseDeepAgent._probe_cross_service ───────────────────────────────────

class _FakeAgent(BaseDeepAgent):
    PRIMARY_VULN_CLASS = "Test"


def _agent():
    graph = AttackGraph()
    asi = AttackSurfaceIndex()
    return _FakeAgent(scan_id="s1", target_url="http://localhost:4001",
                      attack_graph=graph, asi=asi, oracle=None)


@pytest.mark.asyncio
async def test_probe_cross_service_reports_finding_when_accepted():
    agent = _agent()
    agent.graph.confirmed_tokens.append("fake.jwt.token")
    edge = AttackEdge(source="whatsapp-broadcast", target="http://localhost:4002/api/notify",
                       action="cross_service_pivot", priority="critical")

    fake_response = AsyncMock()
    fake_response.status_code = 200
    fake_response.text = "ok"
    fake_client = AsyncMock()
    fake_client.get = AsyncMock(return_value=fake_response)
    fake_client.__aenter__ = AsyncMock(return_value=fake_client)
    fake_client.__aexit__ = AsyncMock(return_value=False)

    with patch("backend.deepagents.base_deep_agent.httpx.AsyncClient", return_value=fake_client):
        await agent._probe_cross_service(edge, ScanContext(target_url=agent.target))

    assert len(agent.vulns) == 1
    assert agent.vulns[0].name == "Cross-Service Credential Reuse"
    assert agent.vulns[0].endpoint == "http://localhost:4002/api/notify"
    fake_client.get.assert_called_once()
    _, kwargs = fake_client.get.call_args
    assert kwargs["headers"]["Authorization"] == "Bearer fake.jwt.token"


@pytest.mark.asyncio
async def test_probe_cross_service_silent_when_rejected():
    agent = _agent()
    agent.graph.confirmed_tokens.append("fake.jwt.token")
    edge = AttackEdge(source="whatsapp-broadcast", target="http://localhost:4002/api/notify",
                       action="cross_service_pivot", priority="critical")

    fake_response = AsyncMock()
    fake_response.status_code = 401
    fake_response.text = "unauthorized"
    fake_client = AsyncMock()
    fake_client.get = AsyncMock(return_value=fake_response)
    fake_client.__aenter__ = AsyncMock(return_value=fake_client)
    fake_client.__aexit__ = AsyncMock(return_value=False)

    with patch("backend.deepagents.base_deep_agent.httpx.AsyncClient", return_value=fake_client):
        await agent._probe_cross_service(edge, ScanContext(target_url=agent.target))

    assert agent.vulns == []


@pytest.mark.asyncio
async def test_probe_cross_service_never_raises_when_sibling_unreachable():
    """Phase 3 (live multi-service deploy) doesn't exist yet — the sibling
    usually isn't actually running. This must degrade silently, not crash
    the scan."""
    agent = _agent()
    agent.graph.confirmed_tokens.append("fake.jwt.token")
    edge = AttackEdge(source="whatsapp-broadcast", target="http://localhost:4002/api/notify",
                       action="cross_service_pivot", priority="critical")

    fake_client = AsyncMock()
    fake_client.get = AsyncMock(side_effect=ConnectionError("no one is listening"))
    fake_client.__aenter__ = AsyncMock(return_value=fake_client)
    fake_client.__aexit__ = AsyncMock(return_value=False)

    with patch("backend.deepagents.base_deep_agent.httpx.AsyncClient", return_value=fake_client):
        await agent._probe_cross_service(edge, ScanContext(target_url=agent.target))

    assert agent.vulns == []
