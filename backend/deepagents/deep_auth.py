from backend.deepagents.base_deep_agent import BaseDeepAgent
from backend.backend.models.scan import ScanContext
from backend.backend.models.agent_result import AgentResult

class DeepAuthAgent(BaseDeepAgent):
    """
    Oracle-guided DeepAgent for Authentication/Authorisation testing.
    Chains findings from the AttackGraph.
    """
    PRIMARY_VULN_CLASS = "Authentication Bypass / Privilege Escalation"

    async def run(self, context: ScanContext) -> AgentResult:
        if not self.asi.endpoints:
            return AgentResult(agent=self.__class__.__name__, vulns=[], context=context)
            
        # We also pass the attack graph state to the Oracle
        has_creds = len(self.graph.confirmed_creds) > 0
        has_tokens = len(self.graph.confirmed_tokens) > 0
        
        if has_creds:
            self.console.print(f"[cyan]DeepAuthAgent[/cyan] found {len(self.graph.confirmed_creds)} confirmed credentials from other agents. Will attempt lateral movement.")
        
        return await super().run(context)
