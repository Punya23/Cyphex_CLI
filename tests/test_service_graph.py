"""Phase 1 microservice discovery: detect sibling service folders, extract
inbound routes + outbound calls, resolve cross-service edges by name, and
round-trip services.yaml. See backend/services/service_discovery.py.
"""
import os

from backend.services.service_discovery import (
    detect_and_build_service_graph,
    detect_services,
    load_services_yaml,
    write_services_yaml,
)
from backend.services.service_graph import ServiceEdge, ServiceGraph, ServiceNode


def _write(path, content=""):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


def _make_two_services(root):
    _write(os.path.join(root, "whatsapp-broadcast", "Dockerfile"), "FROM node:20\n")
    _write(os.path.join(root, "whatsapp-broadcast", "package.json"), "{}")
    _write(os.path.join(root, "whatsapp-broadcast", "index.js"), (
        "const app = require('express')();\n"
        "app.post('/api/broadcast', async (req, res) => {\n"
        "  const r = await fetch(`${process.env.NOTIFICATION_SERVICE_URL}/api/notify`);\n"
        "  res.send(r);\n"
        "});\n"
    ))
    _write(os.path.join(root, "notification-service", "Dockerfile"), "FROM node:20\n")
    _write(os.path.join(root, "notification-service", "package.json"), "{}")
    _write(os.path.join(root, "notification-service", "index.js"), (
        "const app = require('express')();\n"
        "app.post('/api/notify', (req, res) => { res.send('ok'); });\n"
    ))


def test_single_service_repo_is_untouched(tmp_path):
    """The overwhelming common case: no services.yaml, no sibling service
    folders -> None, no file written. Zero behaviour change for mono-repos."""
    _write(tmp_path / "app.py", "x = 1\n")
    graph = detect_and_build_service_graph(str(tmp_path))
    assert graph is None
    assert not (tmp_path / "services.yaml").exists()


def test_detects_two_sibling_services(tmp_path):
    _make_two_services(tmp_path)
    names = {n for n, _ in detect_services(str(tmp_path))}
    assert names == {"whatsapp-broadcast", "notification-service"}


def test_builds_graph_resolves_cross_service_edge_and_writes_yaml(tmp_path):
    _make_two_services(tmp_path)
    graph = detect_and_build_service_graph(str(tmp_path))

    assert graph is not None
    assert graph.auto_generated is True
    assert set(graph.nodes) == {"whatsapp-broadcast", "notification-service"}
    assert graph.nodes["whatsapp-broadcast"].routes == ["/api/broadcast"]
    assert graph.nodes["notification-service"].routes == ["/api/notify"]

    resolved = [e for e in graph.edges if e.target]
    assert len(resolved) == 1
    assert resolved[0].source == "whatsapp-broadcast"
    assert resolved[0].target == "notification-service"

    yaml_path = tmp_path / "services.yaml"
    assert yaml_path.exists()
    assert "whatsapp-broadcast" in yaml_path.read_text(encoding="utf-8")


def test_existing_services_yaml_is_trusted_and_not_rewritten(tmp_path):
    _make_two_services(tmp_path)
    detect_and_build_service_graph(str(tmp_path))  # writes the draft
    written_at = (tmp_path / "services.yaml").stat().st_mtime_ns

    graph = detect_and_build_service_graph(str(tmp_path))

    assert graph.auto_generated is False
    assert (tmp_path / "services.yaml").stat().st_mtime_ns == written_at


def test_unresolved_outbound_call_is_reported_not_dropped(tmp_path):
    _write(tmp_path / "svc-a" / "Dockerfile", "FROM node:20\n")
    _write(tmp_path / "svc-a" / "package.json", "{}")
    _write(tmp_path / "svc-a" / "index.js", (
        "fetch('http://totally-unrelated-host:9/x');\n"
    ))
    _write(tmp_path / "svc-b" / "Dockerfile", "FROM node:20\n")
    _write(tmp_path / "svc-b" / "package.json", "{}")
    _write(tmp_path / "svc-b" / "index.js", "app.get('/x', () => {});\n")

    graph = detect_and_build_service_graph(str(tmp_path))
    assert graph.unresolved_edges(), "an unmatched outbound call must stay, target=''"
    assert graph.to_summary_dict()["unresolved_count"] == len(graph.unresolved_edges())


def test_services_yaml_round_trip_without_pyyaml(tmp_path, monkeypatch):
    """The fallback parser must handle exactly what write_services_yaml emits,
    for installs without PyYAML (see cli_engine's docker-compose precedent)."""
    graph = ServiceGraph(auto_generated=True)
    graph.add_node(ServiceNode(name="svc-a", path="svc-a", base_url="http://localhost:4001"))
    graph.add_node(ServiceNode(name="svc-b", path="svc-b", base_url="http://localhost:4002"))
    yaml_path = tmp_path / "services.yaml"
    write_services_yaml(str(yaml_path), graph)

    import builtins
    real_import = builtins.__import__

    def _no_yaml(name, *a, **kw):
        if name == "yaml":
            raise ImportError("simulated: PyYAML not installed")
        return real_import(name, *a, **kw)

    monkeypatch.setattr(builtins, "__import__", _no_yaml)
    loaded = load_services_yaml(str(yaml_path))
    assert set(loaded.nodes) == {"svc-a", "svc-b"}
    assert loaded.nodes["svc-a"].base_url == "http://localhost:4001"


def test_service_graph_summary_shape():
    graph = ServiceGraph(auto_generated=True)
    graph.add_node(ServiceNode(name="a", path="a", routes=["/x"], language="Python"))
    graph.edges.append(ServiceEdge(source="a", target="", source_route="",
                                    target_hint="http://nope", file="a.py:1"))
    d = graph.to_summary_dict()
    assert d["services"][0]["name"] == "a"
    assert d["edges"][0]["target"] is None
    assert d["unresolved_count"] == 1
