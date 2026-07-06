from backend.deepagents.base_deep_agent import BaseDeepAgent
from backend.backend.models.scan import ScanContext, Vuln
from backend.backend.models.agent_result import AgentResult
from backend.deepagents.oracle_attack import Hypothesis, HttpRequest

class DeepSQLiAgent(BaseDeepAgent):
    """
    Oracle-guided DeepAgent for SQL Injection.
    """
    PRIMARY_VULN_CLASS = "SQL Injection"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    async def run(self, context: ScanContext) -> AgentResult:
        # Before calling Oracle, verify if the surface has any SQLi potential
        if not self.asi.endpoints:
            return AgentResult(agent=self.__class__.__name__, vulns=[], context=context)
            
        has_params = any(p.has_numeric_params or p.has_string_params for p in self.asi.endpoints.values())
        if not has_params and not self.asi.error_signatures:
            # If no parameters and no existing SQL errors observed, skip SQLi
            self.console.print(f"[dim]DeepSQLiAgent skipping: no parameters found in attack surface.[/dim]")
            return AgentResult(agent=self.__class__.__name__, vulns=[], context=context)
            
        return await super().run(context)
