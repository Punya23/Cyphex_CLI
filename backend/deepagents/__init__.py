"""
CYPHEX DeepAgents — Public exports
10 specialized autonomous vulnerability agents using local Ollama models.
"""
from backend.deepagents.deep_sqli import DeepSQLiAgent
from backend.deepagents.deep_xss import DeepXSSAgent
from backend.deepagents.deep_cmdi import DeepCMDiAgent
from backend.deepagents.deep_auth import DeepAuthAgent
from backend.deepagents.deep_idor import DeepIDORAgent
from backend.deepagents.deep_ssrf import DeepSSRFAgent
from backend.deepagents.deep_ssti import DeepSSTIAgent
from backend.deepagents.deep_path_traversal import DeepPathTraversalAgent
from backend.deepagents.deep_xxe import DeepXXEAgent
from backend.deepagents.deep_business_logic import DeepBusinessLogicAgent

__all__ = [
    "DeepSQLiAgent",
    "DeepXSSAgent",
    "DeepCMDiAgent",
    "DeepAuthAgent",
    "DeepIDORAgent",
    "DeepSSRFAgent",
    "DeepSSTIAgent",
    "DeepPathTraversalAgent",
    "DeepXXEAgent",
    "DeepBusinessLogicAgent",
]
