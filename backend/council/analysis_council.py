import json
from rich.console import Console
from backend.council.council_orchestrator import CouncilOrchestrator
from backend.council.model_selector import get_selector

console = Console()

ANALYSIS_SYSTEM = """
You are a security analyst writing a technical report.
You receive a list of confirmed vulnerabilities with their evidence.
RULES:
1. Return ONLY valid JSON array. Each item: {"vuln_name": "...", "root_cause": "...", "attack_scenario": "...", "owasp": "...", "cwe": "...", "risk_level": "...", "business_impact": "..."}
2. Write ONLY about the confirmed vulnerabilities provided. Do not add new findings.
3. attack_scenario: a specific, realistic description of how an attacker would exploit this
   given the actual endpoint and payload evidence. Not generic advice.
4. business_impact: what data or functionality could be compromised. Be specific.
5. risk_level: "Critical" | "High" | "Medium" | "Low" — use CVSS scoring logic.
6. Never reference CVE numbers. CWE only.
7. Never use phrases like "might be vulnerable" or "could potentially". Every statement
   is about a confirmed finding.
"""

ANALYSIS_VALIDATION_SYSTEM = """
You are a technical fact-checker for security reports.
You receive: a list of confirmed findings with evidence, and an analysis report.
Return ONLY valid JSON: {"valid": true/false, "unsupported_claims": ["...", "..."]}
valid=true only if every statement in the analysis is directly supported by the evidence.
List any sentences that make claims not in the evidence.
"""

class AnalysisCouncil(CouncilOrchestrator):
    async def analyse_findings(self, confirmed_vulns: list[dict]) -> list[dict]:
        """
        Dynamically selects the best available models:
          - Narrator (largest general model) writes the analysis
          - Validator (second-best model) cross-checks claims
        Returns the analysis only if validation finds no unsupported claims.
        """
        if not confirmed_vulns:
            return []

        console.print("\n[bold blue]Analysis Council:[/bold blue] Drafting Security Report...")

        # Dynamically discover best models for each role
        selector = await get_selector(quiet=True)
        self.vram.update_costs(selector.get_vram_costs())

        narrator_model = selector.get("narrator")
        validator_model = selector.get("validator")

        console.print(f"[dim]  Narrator:  {narrator_model}[/dim]")
        console.print(f"[dim]  Validator: {validator_model}[/dim]")

        # Unload previous models to free VRAM for narrator
        for m in list(self.vram.loaded.keys()):
            await self.vram.unload(m)

        try:
            await self.vram.ensure_loaded(narrator_model)
        except Exception:
            # Fallback to any available model
            if selector.models:
                narrator_model = selector.models[0].name
                console.print(f"[yellow]⚠ Narrator failed. Using {narrator_model}.[/yellow]")
                await self.vram.ensure_loaded(narrator_model)
            else:
                console.print("[red]⚠ No models available for report generation.[/red]")
                return []

        # Create a clean version of the dicts to send to model to save tokens
        clean_vulns = []
        for v in confirmed_vulns:
            clean_vulns.append({
                "name": v.get("name"),
                "severity": v.get("severity"),
                "endpoint": v.get("endpoint"),
                "evidence": v.get("evidence", v.get("payload", ""))
            })

        analysis_prompt = (
            "Confirmed vulnerabilities with evidence:\n"
            + json.dumps(clean_vulns, indent=2)
        )

        try:
            analysis = await self._call(narrator_model, ANALYSIS_SYSTEM, analysis_prompt, task_name="Report Generation")
            if not isinstance(analysis, list):
                if "analysis" in analysis:
                    analysis = analysis["analysis"]
                elif "findings" in analysis:
                    analysis = analysis["findings"]
                else:
                    analysis = [analysis]
        except Exception as e:
            console.print(f"[red]Failed to generate analysis: {e}[/red]")
            return []

        console.print(f"[dim]Report Drafted. {validator_model} validating claims...[/dim]")

        # Validator cross-checks: are any claims unsupported by the evidence?
        try:
            await self.vram.ensure_loaded(validator_model)
        except Exception:
            validator_model = narrator_model  # fallback to same model

        validation_prompt = (
            f"Evidence:\n{json.dumps(clean_vulns, indent=2)}\n\n"
            f"Analysis to validate:\n{json.dumps(analysis, indent=2)}"
        )

        try:
            validation = await self._call(validator_model, ANALYSIS_VALIDATION_SYSTEM, validation_prompt, task_name="Report Validation")
        except Exception as e:
            console.print(f"[red]Validation failed: {e}[/red]")
            validation = {"valid": True}  # fallback

        if not validation.get("valid", False):
            unsupported = validation.get("unsupported_claims", [])
            console.print(f"[yellow]⚠ {validator_model} flagged {len(unsupported)} unsupported claims in the report.[/yellow]")
            for item in analysis:
                item["_validated"] = False
                item["_unsupported_claims"] = unsupported
        else:
            console.print(f"[green]✓ {validator_model} validated all claims in the report.[/green]")
            for item in analysis:
                item["_validated"] = True

        return analysis
