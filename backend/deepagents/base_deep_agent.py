import time
import httpx
from rich.console import Console

from backend.backend.agents.base_agent import BaseAgent
from backend.backend.models.scan import ScanContext, Vuln
from backend.backend.models.agent_result import AgentResult
from backend.deepagents.attack_graph import AttackGraph
from backend.deepagents.attack_surface_index import AttackSurfaceIndex
from backend.deepagents.oracle_attack import AttackOracle, Hypothesis

console = Console()

class HypothesisResult:
    def __init__(self, confirmed: bool, vuln: Vuln = None):
        self.confirmed = confirmed
        self.vuln = vuln

class BaseDeepAgent(BaseAgent):
    """
    Extends BaseAgent with the full Observe→Think→Act adaptive loop.
    Uses local Ollama only — zero external API dependency.
    """

    MAX_HYPOTHESES = 10
    MAX_ATTEMPTS_PER_HYPOTHESIS = 5
    PRIMARY_VULN_CLASS = "Unknown"

    def __init__(self, scan_id: str, target_url: str, attack_graph: AttackGraph,
                 asi: AttackSurfaceIndex, oracle: AttackOracle, **kwargs):
        super().__init__(scan_id, target_url, **kwargs)
        self.graph = attack_graph          # Shared across all DeepAgents
        self.asi = asi                     # Shared vectorless RAG surface
        self.oracle = oracle               # Per-agent Oracle instance
        self.vulns = []

    async def run(self, context: ScanContext) -> AgentResult:
        console.print(f"[cyan]DeepAgent[/cyan] [yellow]{self.__class__.__name__}[/yellow] initialising against {self.target}...")
        
        # Step 1: Oracle analyses the surface and generates attack plan
        surface_summary = self.asi.summarise_for_prompt()
        console.print(f"[dim]DeepAgent {self.__class__.__name__} consulting Oracle for plan...[/dim]")
        
        try:
            plan = await self.oracle.plan(
                target=self.target,
                surface_summary=surface_summary,
                vuln_class=self.PRIMARY_VULN_CLASS,
            )
            console.print(f"[cyan]Oracle[/cyan] generated plan with {len(plan.hypotheses)} hypotheses.")
        except Exception as e:
            console.print(f"[red]Failed to generate plan for {self.__class__.__name__}: {str(e)}[/red]")
            return AgentResult(agent=self.__class__.__name__, vulns=self.vulns, context=context)

        # Step 2: Execute hypotheses adaptively
        for i, hyp in enumerate(plan.hypotheses[:self.MAX_HYPOTHESES]):
            console.print(f"[dim]Testing hypothesis {i+1}/{len(plan.hypotheses)}: {hyp.vuln_type} on {hyp.test_request.path}[/dim]")
            result = await self._test_hypothesis(hyp, context)
            if result.confirmed and result.vuln:
                self.vulns.append(result.vuln)
                # Update shared graph
                new_edges = self.graph.update_from_finding(result.vuln)
                for edge in new_edges:
                    console.print(f"[green]New Attack Chain Discovered:[/green] {edge.action} from {edge.source} to {edge.target}")

        return AgentResult(
            agent=self.__class__.__name__,
            vulns=self.vulns,
            context=context,
        )

    async def _http_probe(self, request) -> tuple[int, str, float, dict]:
        """Send the HTTP request and measure response time."""
        url = self.target.rstrip('/') + request.path
        if not url.startswith("http"):
             url = f"http://{url}"
             
        start_time = time.time()
        try:
            async with httpx.AsyncClient(timeout=10.0, verify=False) as client:
                headers = request.headers or {}
                if request.method.upper() == "GET":
                     res = await client.get(url, headers=headers)
                elif request.method.upper() == "POST":
                     res = await client.post(url, headers=headers, content=request.body)
                else:
                     res = await client.request(request.method, url, headers=headers, content=request.body)
                     
                elapsed = time.time() - start_time
                return res.status_code, res.text, elapsed, dict(res.headers)
        except Exception as e:
            elapsed = time.time() - start_time
            return 0, str(e), elapsed, {}

    async def _test_hypothesis(self, hyp: Hypothesis, context: ScanContext) -> HypothesisResult:
        for attempt in range(self.MAX_ATTEMPTS_PER_HYPOTHESIS):
            # Execute the probe
            status, body, elapsed, headers = await self._http_probe(hyp.test_request)

            # Update ASI with this response
            self.asi.ingest_response(
                url=hyp.test_request.path,
                method=hyp.test_request.method,
                body=hyp.test_request.body,
                status=status,
                response_body=body,
                headers=headers
            )

            # Oracle decides: confirmed? rejected? try next?
            try:
                decision = await self.oracle.decide(
                    hypothesis=hyp,
                    response_status=status,
                    response_body=body,
                    response_time=elapsed,
                    attempt=attempt,
                )
            except Exception as e:
                console.print(f"[red]Oracle decision failed: {e}[/red]")
                break

            console.print(f"[dim]  Attempt {attempt+1} Oracle decision: {decision.action} ({decision.thinking})[/dim]")

            if decision.action == "confirmed" and decision.vuln:
                vuln = Vuln(
                    name=decision.vuln.get("name", hyp.vuln_type),
                    cwe=decision.vuln.get("cwe", hyp.cwe),
                    severity=decision.vuln.get("severity", hyp.severity),
                    endpoint=hyp.test_request.path,
                    description=f"Confirmed {hyp.vuln_type} on {hyp.test_request.path}",
                    evidence=decision.vuln.get("evidence", ""),
                )
                return HypothesisResult(confirmed=True, vuln=vuln)

            if decision.action == "abandoned":
                return HypothesisResult(confirmed=False)

            if decision.action == "adapt" and decision.next_probe:
                # Oracle generated a better probe — use it
                console.print(f"[yellow]  Adapting payload for next attempt...[/yellow]")
                hyp.test_request = decision.next_probe

        return HypothesisResult(confirmed=False)
