"""CYPHEX ServiceGraph — static cross-service map.

One level above backend.deepagents.attack_graph.AttackGraph: that graph's
nodes/edges are endpoints *inside* one running target; this graph's nodes are
whole services (repos/folders) and its edges are "service A calls service B"
links found in source, not live traffic. Phase 1 only — nothing here talks
to the network.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ServiceNode:
    """One microservice: a folder with its own Dockerfile/manifest."""
    name: str
    path: str                      # relative to the scan's source_dir
    base_url: str = ""             # where it listens, for Phase 3's live scan
    routes: list[str] = field(default_factory=list)       # inbound, e.g. "/api/notify"
    language: str = ""


@dataclass
class ServiceEdge:
    """An outbound call found in `source` service's code toward `target`."""
    source: str                    # ServiceNode.name
    target: str                    # ServiceNode.name, or "" if unresolved
    source_route: str              # route/function the call was found inside, if known
    target_hint: str               # the literal call target text (URL/env var) — kept
                                    # even when target is "" so a human can resolve it
    file: str                      # "path/to/file.py:42"
    confidence: str = "low"        # low | medium | high


@dataclass
class ServiceGraph:
    """The whole static map for one scan. auto_generated marks a graph built
    from folder detection rather than loaded from a user's services.yaml —
    cli_engine uses it to decide whether to print the "wrote services.yaml"
    notice."""
    nodes: dict[str, ServiceNode] = field(default_factory=dict)
    edges: list[ServiceEdge] = field(default_factory=list)
    auto_generated: bool = False

    def add_node(self, node: ServiceNode) -> None:
        self.nodes[node.name] = node

    def unresolved_edges(self) -> list[ServiceEdge]:
        return [e for e in self.edges if not e.target]

    def to_summary_dict(self) -> dict:
        """JSON-report shape — see cli_engine._service_graph_summary()."""
        return {
            "services": [
                {
                    "name": n.name,
                    "path": n.path,
                    "base_url": n.base_url,
                    "routes": n.routes,
                    "language": n.language,
                }
                for n in self.nodes.values()
            ],
            "edges": [
                {
                    "source": e.source,
                    "target": e.target or None,
                    "source_route": e.source_route,
                    "target_hint": e.target_hint,
                    "file": e.file,
                    "confidence": e.confidence,
                }
                for e in self.edges
            ],
            "unresolved_count": len(self.unresolved_edges()),
        }

    def describe(self) -> str:
        """Short human summary printed to the console after discovery."""
        lines = [f"  {len(self.nodes)} service(s): {', '.join(sorted(self.nodes))}"]
        resolved = [e for e in self.edges if e.target]
        if resolved:
            lines.append(f"  {len(resolved)} cross-service call(s) resolved:")
            for e in resolved[:10]:
                lines.append(f"    {e.source} -> {e.target}  ({e.target_hint})")
        unresolved = self.unresolved_edges()
        if unresolved:
            lines.append(
                f"  {len(unresolved)} outbound call(s) could not be matched to a "
                f"known service — add base_url/path hints to services.yaml to fix."
            )
        return "\n".join(lines)
