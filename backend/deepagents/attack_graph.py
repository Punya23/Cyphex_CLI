from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Set

@dataclass
class AttackEdge:
    source: str
    target: str
    action: str
    priority: str

@dataclass
class AttackNode:
    url: str
    known_vulns: List[str] = field(default_factory=list)
    tested_hypotheses: List[str] = field(default_factory=list)

class AttackGraph:
    """
    Shared state across all DeepAgents in a scan session.
    Updated in real-time as findings emerge.
    """

    def __init__(self):
        self.nodes: Dict[str, AttackNode] = {}     # endpoint → what we know
        self.edges: List[AttackEdge] = []          # "finding at A → try B"
        self.confirmed_creds: List[Tuple[str, str, str]] = [] # (user, pwd, source_url)
        self.confirmed_tokens: List[str] = []      # JWTs / session tokens
        self.privilege_level: str = "none"         # none → user → admin

    def get_node(self, url: str) -> AttackNode:
        if url not in self.nodes:
            self.nodes[url] = AttackNode(url=url)
        return self.nodes[url]

    def _extract_token(self, evidence: str) -> str:
        """Helper to extract a token from evidence string."""
        import re
        match = re.search(r'"(?:token|jwt)"\s*:\s*"([^"]+)"', evidence, re.I)
        if match:
            return match.group(1)
        return ""
        
    def _find_auth_endpoints(self) -> List[str]:
        """Find endpoints that likely require authentication."""
        from backend.config.dast_constants import AUTH_KEYWORDS
        return [node for node in self.nodes if any(k in node for k in AUTH_KEYWORDS)]

    def update_from_finding(self, finding) -> List[AttackEdge]:
        """
        When one agent finds something, what should OTHER agents try?
        This is the "chain" logic a real hacker uses.
        Expects a Vuln object (defined in backend.models)
        """
        chains = []
        node = self.get_node(finding.endpoint)
        node.known_vulns.append(finding.name)

        if "SQL Injection" in finding.name and finding.dumped_data:
            # SQLi dumped credentials → try them everywhere
            if ":" in finding.dumped_data:
                user, pwd = finding.dumped_data.split(":", 1)
                self.confirmed_creds.append((user, pwd, finding.endpoint))
                chains.append(AttackEdge(
                    source=finding.endpoint,
                    target="/admin",
                    action="credential_stuffing",
                    priority="critical",
                ))

        if "Sensitive Data" in finding.name and "token" in finding.evidence.lower():
            # Token leaked → try replay on authenticated endpoints
            token = self._extract_token(finding.evidence)
            if token:
                self.confirmed_tokens.append(token)
                auth_targets = self._find_auth_endpoints()
                for target in auth_targets:
                    chains.append(AttackEdge(
                        source=finding.endpoint,
                        target=target,
                        action="token_replay",
                        priority="high",
                    ))

        return chains
