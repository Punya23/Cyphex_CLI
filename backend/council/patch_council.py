import json
from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from backend.council.council_orchestrator import CouncilOrchestrator

console = Console()

PATCH_GENERATION_SYSTEM = """
You are CYPHEX Patch Agent, a secure code analysis assistant.
RULES:
1. Return ONLY valid JSON: {"unsafe_reason": string, "fixed_code": string, "patch_safety": "safe"|"review_needed"}
2. fixed_code must be a drop-in replacement for the vulnerable snippet. Change ONLY what is needed to fix the vulnerability.
3. Do not add imports, do not restructure, do not rename variables unrelated to the fix.
4. unsafe_reason: one sentence explaining why the original code is dangerous in plain English.
5. Never reference CVE numbers.
6. patch_safety = "safe" only if the fix is unambiguous and requires no external context.
"""

PATCH_REVIEW_SYSTEM = """
You are a senior security code reviewer.
You will receive: the vulnerability type, the original vulnerable code, and a proposed patch.
RULES:
1. Return ONLY valid JSON: {"approved": true/false, "reason": "one sentence max 30 words"}
2. approved=true ONLY when ALL of these are true:
   - The patch actually eliminates the vulnerability (parameterised query, escaped output, etc.)
   - The patch does not introduce new security issues
   - The patch does not change logic unrelated to the vulnerability
   - The patch is syntactically valid for the language
3. approved=false if the patch is incomplete, changes too much, or introduces new issues.
"""

class PatchCouncil(CouncilOrchestrator):
    async def generate_and_validate_patch(
        self,
        vuln_name: str,
        cwe: str,
        vulnerable_code: str,
        file_path: str
    ) -> dict:
        """
        Returns patch result dict with keys:
          fixed_code, unsafe_reason, patch_safety, approvals, dissent_reasons
        """
        console.print(f"\n[bold magenta]Patching Vulnerability:[/bold magenta] {vuln_name}")

        # Stage 1: Unload everything, load Qwen-7B alone
        for model in list(self.vram.loaded.keys()):
            await self.vram.unload(model)
        
        try:
            await self.vram.ensure_loaded("cyphex-patch")
            patch_model = "cyphex-patch"
        except Exception:
            console.print("[yellow]⚠ Fine-tuned 'cyphex-patch' not found. Falling back to base 'qwen2.5-coder:7b'[/yellow]")
            await self.vram.ensure_loaded("qwen2.5-coder:7b")
            patch_model = "qwen2.5-coder:7b"

        patch_prompt = (
            f"Vulnerability: {vuln_name} ({cwe})\n"
            f"File: {file_path}\n\n"
            f"Vulnerable code:\n```\n{vulnerable_code}\n```\n\n"
            f"Generate the fixed version of this code."
        )

        console.print("[dim]Stage 1: Qwen-Coder Generating Patch...[/dim]")
        try:
            patch_result = await self._call(patch_model, PATCH_GENERATION_SYSTEM, patch_prompt, task_name="Patch Generation")
        except Exception as e:
            console.print(f"[red]Error generating patch: {e}[/red]")
            return {"fixed_code": "", "patch_safety": "rejected", "unsafe_reason": "Error", "dissent_reasons": ["Generation failed"]}

        fixed_code = patch_result.get("fixed_code", "")
        
        # Display the generated code
        lang = "javascript" if file_path.endswith(".js") or file_path.endswith(".jsx") else "python" if file_path.endswith(".py") else "php" if file_path.endswith(".php") else "python"
        console.print(Panel(Syntax(fixed_code, lang, theme="monokai", line_numbers=True), title="[cyphex-patch] Generated Fix", border_style="green"))

        # Stage 2: Unload Qwen, reload validators
        console.print("[dim]Stage 2 & 3: Deepseek and Phi-3 Validating Patch...[/dim]")
        await self.vram.unload("cyphex-patch")
        await self.vram.ensure_loaded("deepseek-coder:1.3b")
        await self.vram.ensure_loaded("phi3:mini")

        review_prompt = (
            f"Vulnerability: {vuln_name} ({cwe})\n\n"
            f"Original vulnerable code:\n```\n{vulnerable_code}\n```\n\n"
            f"Proposed patch:\n```\n{fixed_code}\n```"
        )

        approvals = []
        for model in ["deepseek-coder:1.3b", "phi3:mini"]:
            try:
                review = await self._call(model, PATCH_REVIEW_SYSTEM, review_prompt, task_name=f"Patch Review ({model})")
                approvals.append({"model": model, **review})
            except Exception as e:
                console.print(f"[red]Error from {model}: {e}[/red]")
                approvals.append({"model": model, "approved": False, "reason": "Error during call"})

        approved_count = sum(1 for a in approvals if a.get("approved", False))
        dissent_reasons = [a["reason"] for a in approvals if not a.get("approved", False)]

        if approved_count == 2:
            final_safety = "safe"
            c = "green"
        elif approved_count == 1:
            final_safety = "review_needed"
            c = "yellow"
        else:
            final_safety = "rejected"
            c = "red"

        console.print(f"[bold {c}]Patch Validation Result: {final_safety.upper()}[/bold {c}]")

        return {
            "fixed_code": fixed_code,
            "unsafe_reason": patch_result.get("unsafe_reason", ""),
            "patch_safety": final_safety,
            "approvals": approvals,
            "dissent_reasons": dissent_reasons,
            "vote_summary": f"{approved_count}/2 validators approved"
        }
