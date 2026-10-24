"""CYPHEX — Phase 1 microservice discovery.

Detects a monorepo-of-services layout (each immediate subfolder has its own
Dockerfile + language manifest), extracts each service's inbound routes and
outbound HTTP calls by regex (same house style as
backend.council.route_tracer / cli_engine's docker-compose parsing — no AST,
no LLM), resolves outbound calls to sibling services by name, and persists
the result as a hand-editable services.yaml.

Entry point: detect_and_build_service_graph(source_dir). Returns None for an
ordinary single-service repo — zero behaviour change there.
"""
from __future__ import annotations

import os
import re

from backend.services.service_graph import ServiceEdge, ServiceGraph, ServiceNode

SKIP_DIRS = {
    "node_modules", ".git", "__pycache__", "venv", ".venv", "dist", "build",
    "sandboxes", ".cyphex", "target", "vendor", ".next", "coverage",
}
_MANIFESTS = ("package.json", "go.mod", "requirements.txt", "pyproject.toml",
              "pom.xml", "composer.json")
_SOURCE_EXTS = (".js", ".ts", ".jsx", ".tsx", ".py", ".go", ".java")

_INBOUND_PATTERNS = [
    # Express/Fastify: app.get('/x'), router.post('/x'), app.use('/x')
    re.compile(r'\.(?:get|post|put|delete|patch|use|all)\s*\(\s*[\'"`](/[^\'"`]*)[\'"`]', re.I),
    # NestJS/Spring: @Get('x'), @RequestMapping('/x')
    re.compile(r'@(?:Get|Post|Put|Delete|Patch|RequestMapping)\s*\(\s*[\'"`](/?[^\'"`]*)[\'"`]\)', re.I),
    # Flask/FastAPI: @app.route('/x'), @router.get('/x')
    re.compile(r'@(?:app|router)\.(?:route|get|post|put|delete|patch)\s*\(\s*[\'"`](/[^\'"`]*)[\'"`]', re.I),
]

# Outbound HTTP calls: JS fetch/axios, Python requests/httpx, Go net/http.
# Capture group 2 is the raw target text — a literal URL, or whatever
# template/f-string/env-var expression the call was given; unresolvable text
# is kept as target_hint rather than discarded (see service_graph.describe).
_OUTBOUND_PATTERNS = [
    re.compile(r'fetch\s*\(\s*([`"\'])(.*?)\1', re.I),
    re.compile(r'axios(?:\.(?:get|post|put|delete|patch))?\s*\(\s*([`"\'])(.*?)\1', re.I),
    re.compile(r'(?:requests|httpx)\.(?:get|post|put|delete|patch)\s*\(\s*([\'"])(.*?)\1', re.I),
    re.compile(r'http\.(?:Get|Post|Put|Delete)\s*\(\s*([\'"])(.*?)\1', re.I),
    re.compile(r'http\.NewRequest\s*\(\s*[\'"][A-Z]+[\'"]\s*,\s*([\'"])(.*?)\1', re.I),
]


def _normalize(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", s.lower())


def detect_services(source_dir: str) -> list[tuple[str, str]]:
    """[(name, relpath)] for each immediate subfolder that looks like an
    independently-buildable service (own Dockerfile + manifest)."""
    found = []
    try:
        entries = sorted(os.listdir(source_dir))
    except OSError:
        return []
    for entry in entries:
        if entry.startswith(".") or entry in SKIP_DIRS:
            continue
        full = os.path.join(source_dir, entry)
        if not os.path.isdir(full):
            continue
        has_dockerfile = os.path.isfile(os.path.join(full, "Dockerfile"))
        has_manifest = any(os.path.isfile(os.path.join(full, m)) for m in _MANIFESTS)
        if has_dockerfile and has_manifest:
            found.append((entry, entry))
    return found


def _guess_language(service_dir: str) -> str:
    if os.path.isfile(os.path.join(service_dir, "go.mod")):
        return "Go"
    if os.path.isfile(os.path.join(service_dir, "pom.xml")):
        return "Java"
    if os.path.isfile(os.path.join(service_dir, "package.json")):
        is_ts = os.path.isfile(os.path.join(service_dir, "tsconfig.json"))
        return "TypeScript" if is_ts else "JavaScript"
    if os.path.isfile(os.path.join(service_dir, "requirements.txt")) or \
       os.path.isfile(os.path.join(service_dir, "pyproject.toml")):
        return "Python"
    return ""


def _iter_source_files(service_dir: str):
    for root, dirs, files in os.walk(service_dir):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS and not d.startswith(".")]
        for name in files:
            if name.endswith(_SOURCE_EXTS):
                full = os.path.join(root, name)
                yield full, os.path.relpath(full, service_dir)


def discover_inbound_routes(service_dir: str) -> list[str]:
    routes: list[str] = []
    seen = set()
    for full, _rel in _iter_source_files(service_dir):
        try:
            with open(full, encoding="utf-8", errors="ignore") as f:
                text = f.read()
        except OSError:
            continue
        for pattern in _INBOUND_PATTERNS:
            for m in pattern.finditer(text):
                route = m.group(1).strip()
                if route and route not in seen:
                    seen.add(route)
                    routes.append(route)
    return routes


def discover_outbound_edges(service_name: str, service_dir: str) -> list[ServiceEdge]:
    """Edges with target="" — the caller resolves target against sibling
    service names."""
    edges = []
    for full, rel in _iter_source_files(service_dir):
        try:
            with open(full, encoding="utf-8", errors="ignore") as f:
                lines = f.readlines()
        except OSError:
            continue
        for i, line in enumerate(lines, 1):
            for pattern in _OUTBOUND_PATTERNS:
                m = pattern.search(line)
                if not m:
                    continue
                hint = m.group(2).strip()
                if not hint or len(hint) < 4:
                    continue
                edges.append(ServiceEdge(
                    source=service_name,
                    target="",
                    source_route="",
                    target_hint=hint,
                    file=f"{rel}:{i}",
                    confidence="medium" if hint.startswith(("http://", "https://")) else "low",
                ))
    return edges


def _resolve_target(hint: str, candidate_names: list[str]) -> str:
    """Match an outbound call's raw target text to a sibling service by
    substring containment on normalized names — covers both a literal
    hostname (http://notification-service:4002/...) and the common
    <NAME>_SERVICE_URL / <NAME>_API_URL env-var convention, since both embed
    the service's own name as a substring."""
    norm_hint = _normalize(hint)
    for name in candidate_names:
        norm_name = _normalize(name)
        if norm_name and norm_name in norm_hint:
            return name
    return ""


def write_services_yaml(path: str, graph: ServiceGraph) -> None:
    lines = [
        "# Auto-generated by CYPHEX from the service folders it found under this repo.",
        "# base_url is a PLACEHOLDER (Phase 1 is static-only — nothing is deployed",
        "# or tested live yet). Edit freely; once this file exists CYPHEX trusts it",
        "# and skips auto-detection on the next scan.",
        "services:",
    ]
    for n in graph.nodes.values():
        lines.append(f"  - name: {n.name}")
        lines.append(f"    path: {n.path}")
        lines.append(f"    base_url: {n.base_url}")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def _parse_services_yaml_fallback(path: str) -> list[dict]:
    """Line-based parser for this file's own fixed shape — used only when
    PyYAML is missing, same fallback convention as cli_engine's
    docker-compose parsing."""
    services: list[dict] = []
    current: dict | None = None
    try:
        with open(path, encoding="utf-8") as f:
            raw_lines = f.readlines()
    except OSError:
        return []
    for raw in raw_lines:
        line = raw.split("#", 1)[0].rstrip()
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("- name:"):
            if current:
                services.append(current)
            current = {"name": stripped.split(":", 1)[1].strip()}
        elif current and stripped.startswith(("path:", "base_url:")):
            key, _, val = stripped.partition(":")
            current[key.strip()] = val.strip()
    if current:
        services.append(current)
    return services


def load_services_yaml(path: str) -> ServiceGraph | None:
    try:
        import yaml
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        services = data.get("services") or []
    except ImportError:
        services = _parse_services_yaml_fallback(path)
    except Exception:
        return None

    graph = ServiceGraph(auto_generated=False)
    for svc in services:
        if not isinstance(svc, dict) or not svc.get("name"):
            continue
        name = str(svc["name"])
        graph.add_node(ServiceNode(
            name=name,
            path=str(svc.get("path") or name),
            base_url=str(svc.get("base_url") or ""),
        ))
    return graph if graph.nodes else None


def detect_and_build_service_graph(source_dir: str) -> ServiceGraph | None:
    """cli_engine.py calls this right after resolving source_dir. Returns
    None for an ordinary single-service repo (no services.yaml, fewer than 2
    detected service folders) — identical to today's scan in that case.
    Never raises: a bug here must degrade, not abort the scan."""
    try:
        yaml_path = os.path.join(source_dir, "services.yaml")
        if os.path.isfile(yaml_path):
            graph = load_services_yaml(yaml_path)
            if graph is None:
                return None
        else:
            detected = detect_services(source_dir)
            if len(detected) < 2:
                return None
            graph = ServiceGraph(auto_generated=True)
            for i, (name, rel) in enumerate(detected):
                graph.add_node(ServiceNode(
                    name=name, path=rel, base_url=f"http://localhost:{4001 + i}",
                ))

        names = list(graph.nodes)
        for node in graph.nodes.values():
            service_dir = os.path.join(source_dir, node.path)
            node.routes = discover_inbound_routes(service_dir)
            node.language = _guess_language(service_dir)
            for edge in discover_outbound_edges(node.name, service_dir):
                edge.target = _resolve_target(edge.target_hint,
                                               [n for n in names if n != node.name])
                graph.edges.append(edge)

        if graph.auto_generated:
            write_services_yaml(yaml_path, graph)
        return graph
    except Exception:
        return None
