from backend.deepagents.base_deep_agent import BaseDeepAgent
from backend.backend.models.scan import ScanContext
from backend.backend.models.agent_result import AgentResult

class DeepSQLiAgent(BaseDeepAgent):
    """
    Oracle-guided DeepAgent for SQL Injection.
    """
    PRIMARY_VULN_CLASS = "SQL Injection"

class DeepXSSAgent(BaseDeepAgent):
    """
    Oracle-guided DeepAgent for Cross-Site Scripting.
    """
    PRIMARY_VULN_CLASS = "Cross-Site Scripting (XSS)"

class DeepCMDiAgent(BaseDeepAgent):
    """
    Oracle-guided DeepAgent for Command Injection.
    """
    PRIMARY_VULN_CLASS = "Command Injection"

class DeepAuthAgent(BaseDeepAgent):
    """
    Oracle-guided DeepAgent for Authentication/Authorisation testing.
    Chains findings from the AttackGraph.
    """
    PRIMARY_VULN_CLASS = "Authentication Bypass / Privilege Escalation"
