from backend.deepagents.base_deep_agent import BaseDeepAgent
from backend.backend.models.scan import ScanContext
from backend.backend.models.agent_result import AgentResult

class DeepXSSAgent(BaseDeepAgent):
    """
    Oracle-guided DeepAgent for Cross-Site Scripting.
    """
    PRIMARY_VULN_CLASS = "Cross-Site Scripting (XSS)"

    async def run(self, context: ScanContext) -> AgentResult:
        if not self.asi.endpoints:
            return AgentResult(agent=self.__class__.__name__, vulns=[], context=context)
            
        has_string_params = any(p.has_string_params for p in self.asi.endpoints.values())
        if not has_string_params:
            self.console.print(f"[dim]DeepXSSAgent skipping: no string parameters found in attack surface.[/dim]")
            return AgentResult(agent=self.__class__.__name__, vulns=[], context=context)
            
        return await super().run(context)
