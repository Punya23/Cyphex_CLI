"""CYPHEX — Phase 3 microservice VAPT: deploy every detected service on one
Docker network, so a Phase 2 cross_service_pivot target is actually live
instead of a guess.

Reuses cyphex.docker_sandbox's exact build/run/health-check shape (same
resource limits, same "Up" + real-port health check, same honest
status-on-failure convention), extended to N services on one shared
user-defined bridge network with a Docker network alias per service — so
both a literal hostname call (http://notification-service:4002/...) and the
<NAME>_SERVICE_URL env-var convention Phase 1 already extracts resolve to
the real sibling container.
"""
from __future__ import annotations

import asyncio
import os
import re
import subprocess

from cyphex.docker_sandbox import (
    _check_up,
    _detect_app_type,
    _generate_dockerfile,
    _find_free_port,
    docker_available,
)


def _container_name(scan_id: str, service_name: str) -> str:
    return f"cyphex-svc-{scan_id}-{service_name}"


def _network_name(scan_id: str) -> str:
    return f"cyphex-net-{scan_id}"


def _env_var_override(edge, graph, app_info_by_name) -> tuple[str, str] | None:
    """One -e KEY=value override for an outbound edge whose target_hint
    looks like the <NAME>_SERVICE_URL / <NAME>_API_URL env-var convention
    (first ALL_CAPS identifier in the hint). Points it at the sibling
    service's Docker network alias — its short name on the shared network,
    not its host port — so the call actually reaches it from inside the
    container. Literal-hostname edges (no caps identifier) need no override:
    the alias on the target's own container already answers to its name."""
    match = re.search(r"[A-Z][A-Z0-9_]{3,}", edge.target_hint)
    if not match:
        return None
    target_node = graph.nodes.get(edge.target)
    if not target_node:
        return None
    internal_port = app_info_by_name.get(target_node.name, {}).get("port", 8080)
    return match.group(0), f"http://{target_node.name}:{internal_port}"


async def deploy_service_graph(source_dir: str, graph, scan_id: str) -> dict:
    """Build + run every node in `graph` as its own container on one shared
    network. On success, sets node.base_url to the live host-reachable URL
    (what CYPHEX's own agents, running on the host, use to reach it) — a
    node that fails to deploy keeps whatever placeholder base_url it had and
    is listed in "failed", never silently treated as live.

    Returns {"network", "containers", "deployed", "failed"}. Always pass the
    result to teardown_service_graph() when done, success or not."""
    if not docker_available():
        return {"network": "", "containers": [], "deployed": [],
                "failed": list(graph.nodes), "error": "Docker not available"}

    network_name = _network_name(scan_id)
    await asyncio.to_thread(
        subprocess.run, ["docker", "network", "create", network_name],
        capture_output=True, text=True, timeout=15,
    )  # "already exists" (concurrent scan, or a leaked prior network) is fine

    app_info_by_name: dict[str, dict] = {}
    generated_dockerfiles: list[str] = []
    for node in graph.nodes.values():
        service_dir = os.path.join(source_dir, node.path)
        app_info_by_name[node.name] = _detect_app_type(service_dir)
        dockerfile_path = os.path.join(service_dir, "Dockerfile")
        if not os.path.exists(dockerfile_path):
            with open(dockerfile_path, "w", encoding="utf-8") as f:
                f.write(_generate_dockerfile(service_dir, app_info_by_name[node.name]))
            generated_dockerfiles.append(dockerfile_path)

    containers: list[str] = []
    deployed: list[str] = []
    failed: list[str] = []
    try:
        for node in graph.nodes.values():
            service_dir = os.path.join(source_dir, node.path)
            container_name = _container_name(scan_id, node.name)
            containers.append(container_name)
            host_port = _find_free_port()
            internal_port = app_info_by_name[node.name]["port"]

            build = await asyncio.to_thread(
                subprocess.run, ["docker", "build", "-t", container_name, "."],
                cwd=service_dir, capture_output=True, text=True, timeout=180,
            )
            if build.returncode != 0:
                failed.append(node.name)
                continue

            run_cmd = [
                "docker", "run", "-d",
                "--name", container_name,
                "--network", network_name,
                "--network-alias", node.name,
                "--memory", "512m",
                "--cpus", "1",
                "--pids-limit", "200",
                "--cap-drop", "ALL",
                "--security-opt", "no-new-privileges",
                "-p", f"127.0.0.1:{host_port}:{internal_port}",
                "-e", f"PORT={internal_port}",
            ]
            seen_vars = set()
            for edge in graph.edges:
                if edge.source != node.name or not edge.target:
                    continue
                override = _env_var_override(edge, graph, app_info_by_name)
                if override and override[0] not in seen_vars:
                    seen_vars.add(override[0])
                    run_cmd += ["-e", f"{override[0]}={override[1]}"]
            run_cmd.append(container_name)

            run = await asyncio.to_thread(
                subprocess.run, run_cmd, capture_output=True, text=True, timeout=30,
            )
            if run.returncode != 0:
                failed.append(node.name)
                continue

            url = f"http://localhost:{host_port}"
            await asyncio.sleep(2)
            if await _check_up(url):
                node.base_url = url
                deployed.append(node.name)
            else:
                failed.append(node.name)
    finally:
        for path in generated_dockerfiles:
            if os.path.exists(path):
                os.remove(path)

    return {"network": network_name, "containers": containers,
            "deployed": deployed, "failed": failed}


def teardown_service_graph(result: dict) -> None:
    """Stop+remove every container deploy_service_graph started (deployed or
    failed — a failed run can still have left a container behind) and the
    shared network. Best-effort: a stray container is a cleanup nuisance,
    never a reason to fail the scan that already ran."""
    for container_name in result.get("containers") or []:
        try:
            subprocess.run(["docker", "rm", "-f", container_name],
                           capture_output=True, text=True, timeout=15)
        except Exception:
            pass
    network_name = result.get("network")
    if network_name:
        try:
            subprocess.run(["docker", "network", "rm", network_name],
                           capture_output=True, text=True, timeout=15)
        except Exception:
            pass
