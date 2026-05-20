import json
from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from backend.council.council_orchestrator import CouncilOrchestrator
from backend.council.model_selector import get_selector

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
        Dynamically selects models:
          - Patcher: best coding model (generates the fix)
          - Reviewers: 2 distinct models (validate the fix)

        Returns patch result dict with keys:
          fixed_code, unsafe_reason, patch_safety, approvals, dissent_reasons
        """
        console.print(f"\n[bold magenta]Patching Vulnerability:[/bold magenta] {vuln_name}")

        # Dynamically discover best models
        selector = await get_selector(quiet=True)
        self.vram.update_costs(selector.get_vram_costs())

        patch_model = selector.get("patcher")
        reviewer_models = selector.get_validators(count=2)

        console.print(f"[dim]  Patcher:   {patch_model}[/dim]")
        console.print(f"[dim]  Reviewers: {', '.join(reviewer_models)}[/dim]")

        # Stage 1: Unload everything, load patcher
        for model in list(self.vram.loaded.keys()):
            await self.vram.unload(model)

        try:
            await self.vram.ensure_loaded(patch_model)
        except Exception:
            # Fallback to any available model
            if selector.models:
                patch_model = selector.models[0].name
                console.print(f"[yellow]⚠ Patcher failed. Using {patch_model}.[/yellow]")
                await self.vram.ensure_loaded(patch_model)
            else:
                return {"fixed_code": "", "patch_safety": "rejected",
                        "unsafe_reason": "No models available", "dissent_reasons": ["No Ollama models"]}

        patch_prompt = (
            f"Vulnerability: {vuln_name} ({cwe})\n"
            f"File: {file_path}\n\n"
            f"Vulnerable code:\n```\n{vulnerable_code}\n```\n\n"
            f"Generate the fixed version of this code."
        )

        console.print(f"[dim]Stage 1: {patch_model} Generating Patch...[/dim]")
        try:
            patch_result = await self._call(patch_model, PATCH_GENERATION_SYSTEM, patch_prompt, task_name="Patch Generation")
        except Exception as e:
            console.print(f"[red]Error generating patch: {e}[/red]")
            return {"fixed_code": "", "patch_safety": "rejected", "unsafe_reason": "Error", "dissent_reasons": ["Generation failed"]}

        fixed_code = patch_result.get("fixed_code", "")

        # Display the generated code
        lang = "javascript" if file_path.endswith((".js", ".jsx")) else "python" if file_path.endswith(".py") else "php" if file_path.endswith(".php") else "python"
        console.print(Panel(Syntax(fixed_code, lang, theme="monokai", line_numbers=True), title=f"[{patch_model}] Generated Fix", border_style="green"))

        # Stage 2: Unload patcher, reload reviewers
        console.print(f"[dim]Stage 2: {' & '.join(reviewer_models)} Validating Patch...[/dim]")
        await self.vram.unload(patch_model)

        review_prompt = (
            f"Vulnerability: {vuln_name} ({cwe})\n\n"
            f"Original vulnerable code:\n```\n{vulnerable_code}\n```\n\n"
            f"Proposed patch:\n```\n{fixed_code}\n```"
        )

        approvals = []
        for model in reviewer_models:
            try:
                await self.vram.ensure_loaded(model)
                review = await self._call(model, PATCH_REVIEW_SYSTEM, review_prompt, task_name=f"Patch Review ({model})")
                approvals.append({"model": model, **review})
            except Exception as e:
                console.print(f"[red]Error from {model}: {e}[/red]")
                approvals.append({"model": model, "approved": False, "reason": "Error during call"})

        approved_count = sum(1 for a in approvals if a.get("approved", False))
        total_reviewers = len(approvals)
        dissent_reasons = [a["reason"] for a in approvals if not a.get("approved", False)]

        if approved_count == total_reviewers:
            final_safety = "safe"
            c = "green"
        elif approved_count >= 1:
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
            "vote_summary": f"{approved_count}/{total_reviewers} validators approved"
        }

    async def generate_and_validate_batch(self, vuln_list: list[dict]) -> list[dict]:
        """
        Agent-Centric Batching: loads each model ONCE and processes ALL vulnerabilities
        before swapping. Reduces model swaps from O(N*Agents) to O(Agents).

        vuln_list: list of dicts with keys: vuln_name, cwe, vulnerable_code, file_path
        Returns: list of patch result dicts (same format as generate_and_validate_patch)
        """
        if not vuln_list:
            return []

        console.print(f"\n[bold magenta]═══ Batch Patch Mode: {len(vuln_list)} vulnerabilities ═══[/bold magenta]")

        # Discover models
        selector = await get_selector(quiet=True)
        self.vram.update_costs(selector.get_vram_costs())
        patch_model = selector.get("patcher")
        reviewer_models = selector.get_validators(count=2)

        console.print(f"[dim]  Patcher:   {patch_model}[/dim]")
        console.print(f"[dim]  Reviewers: {', '.join(reviewer_models)}[/dim]")

        # ── Stage 1: Load patcher ONCE, generate ALL patches ──
        console.print(f"\n[bold cyan]Stage 1/3: Generating {len(vuln_list)} patches ({patch_model})[/bold cyan]")
        for model in list(self.vram.loaded.keys()):
            await self.vram.unload(model)

        try:
            await self.vram.ensure_loaded(patch_model)
        except Exception:
            if selector.models:
                patch_model = selector.models[0].name
                console.print(f"[yellow]⚠ Patcher failed. Using {patch_model}.[/yellow]")
                await self.vram.ensure_loaded(patch_model)
            else:
                return [{"fixed_code": "", "patch_safety": "rejected",
                         "unsafe_reason": "No models available"} for _ in vuln_list]

        patch_results = []
        for i, v in enumerate(vuln_list, 1):
            console.print(f"[dim]  [{i}/{len(vuln_list)}] Patching: {v['vuln_name']}[/dim]")
            prompt = (
                f"Vulnerability: {v['vuln_name']} ({v['cwe']})\n"
                f"File: {v['file_path']}\n\n"
                f"Vulnerable code:\n```\n{v['vulnerable_code']}\n```\n\n"
                f"Generate the fixed version of this code."
            )
            try:
                result = await self._call(patch_model, PATCH_GENERATION_SYSTEM, prompt, task_name="Batch Patch")
                patch_results.append(result)
            except Exception as e:
                console.print(f"[red]  Error: {e}[/red]")
                patch_results.append({"fixed_code": "", "unsafe_reason": "Generation failed"})

        # ── Stage 2 & 3: Load each reviewer ONCE, review ALL patches ──
        await self.vram.unload(patch_model)

        all_approvals = [[] for _ in vuln_list]  # per-vuln approval lists

        for r_idx, reviewer in enumerate(reviewer_models, 2):
            console.print(f"\n[bold cyan]Stage {r_idx}/3: Reviewing ALL patches ({reviewer})[/bold cyan]")
            try:
                await self.vram.ensure_loaded(reviewer)
            except Exception:
                console.print(f"[yellow]⚠ Could not load {reviewer}, skipping.[/yellow]")
                for approvals in all_approvals:
                    approvals.append({"model": reviewer, "approved": False, "reason": "Model load failed"})
                continue

            for i, (v, patch_res) in enumerate(zip(vuln_list, patch_results)):
                fixed_code = patch_res.get("fixed_code", "")
                if not fixed_code:
                    all_approvals[i].append({"model": reviewer, "approved": False, "reason": "No code to review"})
                    continue

                review_prompt = (
                    f"Vulnerability: {v['vuln_name']} ({v['cwe']})\n\n"
                    f"Original vulnerable code:\n```\n{v['vulnerable_code']}\n```\n\n"
                    f"Proposed patch:\n```\n{fixed_code}\n```"
                )
                try:
                    review = await self._call(reviewer, PATCH_REVIEW_SYSTEM, review_prompt, task_name=f"Batch Review")
                    all_approvals[i].append({"model": reviewer, **review})
                except Exception as e:
                    all_approvals[i].append({"model": reviewer, "approved": False, "reason": f"Error: {str(e)[:40]}"})

            await self.vram.unload(reviewer)

        # ── Assemble final results ──
        final_results = []
        for i, (patch_res, approvals) in enumerate(zip(patch_results, all_approvals)):
            approved_count = sum(1 for a in approvals if a.get("approved", False))
            total_reviewers = len(approvals)
            dissent_reasons = [a["reason"] for a in approvals if not a.get("approved", False)]

            if approved_count == total_reviewers:
                final_safety = "safe"
            elif approved_count >= 1:
                final_safety = "review_needed"
            else:
                final_safety = "rejected"

            final_results.append({
                "fixed_code": patch_res.get("fixed_code", ""),
                "unsafe_reason": patch_res.get("unsafe_reason", ""),
                "patch_safety": final_safety,
                "approvals": approvals,
                "dissent_reasons": dissent_reasons,
                "vote_summary": f"{approved_count}/{total_reviewers} validators approved"
            })

        console.print(f"\n[bold green]═══ Batch complete: {len(final_results)} patches processed ═══[/bold green]")
        return final_results
