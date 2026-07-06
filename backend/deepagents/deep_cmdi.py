from backend.deepagents.base_deep_agent import BaseDeepAgent
from backend.backend.models.scan import ScanContext
from backend.backend.models.agent_result import AgentResult

class DeepCMDiAgent(BaseDeepAgent):
    """
    Oracle-guided DeepAgent for Command Injection.
    """
    PRIMARY_VULN_CLASS = "Command Injection"

    async def run(self, context: ScanContext) -> AgentResult:
        if not self.asi.endpoints:
            return AgentResult(agent=self.__class__.__name__, vulns=[], context=context)
            
        return await super().run(context)
