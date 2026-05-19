import json
from rich.console import Console
from backend.council.council_orchestrator import CouncilOrchestrator

console = Console()

VALIDATION_SYSTEM = """
You are a security vulnerability validator on a review council.
You receive: a vulnerability type, the HTTP request sent, and the HTTP response received.

STRICT RULES:
1. Respond ONLY with valid JSON: {"confirmed": true/false, "confidence": 0.0-1.0, "reason": "one sentence max 30 words"}
2. confirmed=true ONLY when the response body contains hard evidence:
   - SQLi: SQL error string present OR response time > 4.5s on SLEEP payload
   - XSS: exact injected payload string appears unescaped in response HTML
   - CMDi: OS command output present (uid=, root, www-data, Directory of)
   - LFI: /etc/passwd content present (root:x:0:0)
   - Auth: auth token/cookie set OR redirect to protected route
   - Missing header: header is absent (always confirmed=true)
3. confirmed=false if evidence is a 500 error alone, a vague change in response, or your suspicion.
4. Never reference CVE numbers. Never guess.
"""

class DebateProtocol(CouncilOrchestrator):
    async def debate_finding(self, vuln_name: str, evidence: str) -> tuple[bool, float, list[dict]]:
        """
        Returns: (confirmed: bool, avg_confidence: float, vote_log: list)
        """
        VALIDATORS = ["deepseek-coder:1.3b", "phi3:mini", "llama3.2:3b"]

        console.print(f"\n[bold cyan]Debating finding: {vuln_name}[/bold cyan]")
        
        # Load narration models for this phase
        for i, model in enumerate(VALIDATORS):
            try:
                await self.vram.ensure_loaded(model)
            except Exception:
                console.print(f"[yellow]⚠ {model} not found. Falling back to phi3:mini.[/yellow]")
                await self.vram.ensure_loaded("phi3:mini")
                VALIDATORS[i] = "phi3:mini"

        prompt = f"Vulnerability type: {vuln_name}\n\nEvidence (request + response):\n{evidence}"

        # Round 1: independent votes
        console.print("[dim]Starting Round 1 Voting...[/dim]")
        votes = []
        for model in VALIDATORS:
            try:
                vote = await self._call(model, VALIDATION_SYSTEM, prompt, task_name="Debate Round 1")
                votes.append({"model": model, "round": 1, **vote})
            except Exception as e:
                console.print(f"[red]Error from {model}: {e}[/red]")
                votes.append({"model": model, "round": 1, "confirmed": False, "confidence": 0.0, "reason": "Error during call"})

        confirmed_count = sum(1 for v in votes if v.get("confirmed", False))

        # Early exit: unanimous
        if confirmed_count == 3 or confirmed_count == 0:
            avg_conf = sum(v.get("confidence", 0.5) for v in votes) / 3
            result = confirmed_count == 3
            c = "green" if result else "red"
            console.print(f"[bold {c}]Debate Concluded (Unanimous): {result}[/bold {c}]")
            return result, avg_conf, votes

        # Round 2: re-prompt dissenters
        console.print("[dim]Starting Round 2 Voting (Re-evaluating Dissenters)...[/dim]")
        majority_view = confirmed_count >= 2
        majority_reasons = [
            v["reason"] for v in votes
            if v.get("confirmed", False) == majority_view
        ]

        for i, vote in enumerate(votes):
            if vote.get("confirmed", False) != majority_view:
                re_prompt = (
                    f"Vulnerability type: {vuln_name}\n\nEvidence:\n{evidence}\n\n"
                    f"The other council members noted: {' | '.join(majority_reasons)}\n"
                    f"Reconsider your verdict with this context. Same JSON format."
                )
                try:
                    re_vote = await self._call(vote["model"], VALIDATION_SYSTEM, re_prompt, task_name="Debate Round 2")
                    votes[i] = {"model": vote["model"], "round": 2, **re_vote}
                except Exception as e:
                    console.print(f"[red]Error from {vote['model']} in round 2: {e}[/red]")

        final_confirmed = sum(1 for v in votes if v.get("confirmed", False))
        avg_conf = sum(v.get("confidence", 0.5) for v in votes) / 3
        result = final_confirmed >= 2
        c = "green" if result else "red"
        console.print(f"[bold {c}]Debate Concluded (Majority): {result}[/bold {c}]")
        
        return result, avg_conf, votes
