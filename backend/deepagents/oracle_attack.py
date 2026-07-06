import json
import re
from dataclasses import dataclass
from typing import List, Dict, Any

from backend.council.council_orchestrator import CouncilOrchestrator

ORACLE_ATTACK_SYSTEM = """
You are CYPHEX DeepAttack Oracle — an elite red team reasoning engine.

Given observations about a web target, you:
1. Identify the most likely vulnerability class
2. Decompose it into testable hypotheses (smallest falsifiable unit)
3. Order hypotheses by: highest CVSS potential FIRST, cheapest test FIRST
4. Specify the exact HTTP request to test each hypothesis
5. Define what response would CONFIRM vs REJECT each hypothesis

Return ONLY valid JSON:
{
  "target_summary": "1 sentence about what this endpoint does",
  "primary_vulnerability_class": "SQLi|XSS|IDOR|CMDi|...",
  "hypotheses": [
    {
      "id": "h1",
      "vuln_type": "Time-Based SQLi",
      "cwe": "CWE-89",
      "severity": "Critical",
      "test_request": {
        "method": "POST",
        "path": "/api/login",
        "body": "username=admin'%3B+SELECT+SLEEP(5)--&password=x",
        "headers": {}
      },
      "confirm_signal": "response_time > 4.5 seconds",
      "reject_signal": "response_time < 1 second AND status != 500",
      "next_if_confirmed": "h2_union_extraction",
      "next_if_rejected": "h3_boolean_sqli"
    }
  ]
}
"""

ORACLE_DECIDE_SYSTEM = """
You are CYPHEX DeepAttack Oracle.
Evaluate the response to a security probe and decide the next action.

Decide one of three actions:
1. "confirmed": The response unequivocally confirms the vulnerability.
2. "abandoned": The target is clearly not vulnerable to this class (e.g. static file, WAF blocked).
3. "adapt": The probe failed but the vulnerability is still possible (e.g. syntax error, needs encoding). Provide the adapted probe.

Return ONLY valid JSON:
{
  "thinking": "1 sentence reasoning",
  "action": "confirmed|abandoned|adapt",
  "vuln": {
    "name": "SQL Injection",
    "cwe": "CWE-89",
    "severity": "Critical",
    "evidence": "Observed syntax error..."
  },
  "next_probe": {
    "method": "GET",
    "path": "...",
    "body": "..."
  }
}
Note: 'vuln' is only needed if action=confirmed. 'next_probe' is only needed if action=adapt.
"""

@dataclass
class HttpRequest:
    method: str
    path: str
    body: str = ""
    headers: dict = None
    
    def summary(self) -> str:
        return f"{self.method} {self.path}"

@dataclass
class Hypothesis:
    id: str
    vuln_type: str
    cwe: str
    severity: str
    test_request: HttpRequest
    confirm_signal: str
    reject_signal: str

@dataclass
class AttackPlan:
    target_summary: str
    primary_vulnerability_class: str
    hypotheses: List[Hypothesis]

    @classmethod
    def from_json(cls, data: dict) -> 'AttackPlan':
        hypotheses = []
        for h in data.get("hypotheses", []):
            req = h.get("test_request", {})
            hypotheses.append(Hypothesis(
                id=h.get("id", ""),
                vuln_type=h.get("vuln_type", ""),
                cwe=h.get("cwe", ""),
                severity=h.get("severity", "Medium"),
                test_request=HttpRequest(
                    method=req.get("method", "GET"),
                    path=req.get("path", ""),
                    body=req.get("body", ""),
                    headers=req.get("headers", {})
                ),
                confirm_signal=h.get("confirm_signal", ""),
                reject_signal=h.get("reject_signal", "")
            ))
        return cls(
            target_summary=data.get("target_summary", ""),
            primary_vulnerability_class=data.get("primary_vulnerability_class", ""),
            hypotheses=hypotheses
        )

@dataclass
class Decision:
    action: str
    thinking: str
    vuln: dict = None
    next_probe: HttpRequest = None

    @classmethod
    def from_json(cls, data: dict) -> 'Decision':
        next_probe = None
        if data.get("next_probe"):
            req = data["next_probe"]
            next_probe = HttpRequest(
                method=req.get("method", "GET"),
                path=req.get("path", ""),
                body=req.get("body", ""),
                headers=req.get("headers", {})
            )
        return cls(
            action=data.get("action", "abandoned"),
            thinking=data.get("thinking", ""),
            vuln=data.get("vuln"),
            next_probe=next_probe
        )

class AttackOracle:
    """
    Wraps the existing LLM orchestrator for DeepAgent attack reasoning.
    """
    
    def __init__(self, orchestrator: CouncilOrchestrator):
        self.orchestrator = orchestrator

    async def plan(self, target: str, surface_summary: str, vuln_class: str, model: str = "qwen2.5-coder:7b") -> AttackPlan:
        prompt = (
            f"Target: {target}\\n\\n"
            f"Vulnerability class to test: {vuln_class}\\n\\n"
            f"Observed attack surface:\\n{surface_summary}\\n\\n"
            "Generate a prioritised, hypothesis-driven attack plan."
        )
        
        response = await self.orchestrator._call(
            model=model,
            system=ORACLE_ATTACK_SYSTEM,
            prompt=prompt,
            task_name="Reasoning"
        )
        return AttackPlan.from_json(response)

    async def decide(self, hypothesis: Hypothesis, response_status: int, response_body: str, 
                     response_time: float, attempt: int, model: str = "qwen2.5-coder:7b") -> Decision:
        prompt = (
            f"Hypothesis: {hypothesis.vuln_type} at {hypothesis.test_request.path}\\n"
            f"Attempt: {attempt + 1}\\n"
            f"Test sent: {hypothesis.test_request.summary()}\\n"
            f"Response: HTTP {response_status}, {len(response_body)} bytes, {response_time:.2f}s\\n"
            f"Response body (first 500 chars): {response_body[:500]}\\n\\n"
            f"Confirmation signal: {hypothesis.confirm_signal}\\n"
            f"Rejection signal: {hypothesis.reject_signal}\\n\\n"
            "Decide: confirmed / adapt (provide next probe) / abandoned"
        )
        
        response = await self.orchestrator._call(
            model=model,
            system=ORACLE_DECIDE_SYSTEM,
            prompt=prompt,
            task_name="Reasoning"
        )
        return Decision.from_json(response)
