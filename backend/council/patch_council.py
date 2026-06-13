import json
from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from backend.council.council_orchestrator import CouncilOrchestrator
from backend.council.model_selector import get_selector

console = Console()

# ── Oracle Reasoning System ───────────────────────────────────────────────────
# Called BEFORE patch generation. Same model, same VRAM session — zero extra
# cost. Forces the small model to decompose the problem before generating code,
# which measurably improves patch quality on 6-8B parameter models.
ORACLE_SYSTEM = """
You are CYPHEX Oracle — a vulnerability reasoning engine.
Your ONLY job: analyse a vulnerability and produce a structured decomposition that
a code-generation agent will use to write the fix.

Return ONLY valid JSON with these exact keys:
{
  "thinking": "1-2 sentences of chain-of-thought",
  "attack_vector": "how an attacker exploits this specific code",
  "data_flow": "trace from user-controlled input to the vulnerable sink (e.g. req.query.id → db.query template literal)",
  "minimal_fix": "the exact minimal change that eliminates the vulnerability — be specific about the code pattern, not general advice",
  "avoid": ["list of naive/wrong fixes that would be rejected (e.g. 'commenting out the route')"],
  "confidence": 0.0
}

Be concrete. Reference the actual variable names, function calls, and line patterns from the code.
Never invent CVE IDs. Never use CWE numbers not in: CWE-89,79,78,22,798,306,942,287,284,918,250.
"""

PATCH_GENERATION_SYSTEM = """
You are CYPHEX Patch Agent, a secure code analysis assistant.
RULES:
1. Return ONLY valid JSON: {"unsafe_reason": string, "fixed_code": string, "patch_safety": "safe"|"review_needed"}
2. fixed_code must be a COMPLETE drop-in replacement for the vulnerable snippet. Change ONLY what is needed to fix the vulnerability.
3. Do not add imports unless strictly required, do not restructure, do not rename variables.
4. IMPORTANT: Provide REAL, WORKING code. Never use pseudo-code, comments-as-placeholders, or stubs like "// add auth logic here".
5. unsafe_reason: one sentence explaining why the original code is dangerous.
6. patch_safety = "safe" only if the fix is unambiguous.

ANTI-REGRESSION RULES (violating these gets the patch rejected):
- Never remove existing try/catch blocks or error handling.
- Never add new import/require statements in the MIDDLE of a function. If an import is
  strictly required, assume it already exists at the top of the file.
- Never "fix" a vulnerability by deleting or commenting-out a route, handler, or feature.
  A commented-out line is NOT a valid fix and will be rejected.
- Preserve the function signature, return type, and surrounding control flow.

VULNERABILITY-SPECIFIC FIX PATTERNS (use these):
- SQL Injection: Replace template literals with parameterized queries using ? placeholders and [value] arrays.
- XSS: Remove dangerouslySetInnerHTML entirely. Render content as text children: <h3>{a.title}</h3> instead of dangerouslySetInnerHTML={{__html: a.title}}.
- Hardcoded Secrets: Replace literal values with ${ENV_VAR} references. Example: MYSQL_ROOT_PASSWORD: ${MYSQL_ROOT_PASSWORD}
- Sensitive Data Exposure (debug routes): Guard the route behind an authentication/role check (e.g. require an admin role before the handler runs). Do NOT comment out or delete the route registration.
- SSRF: Add URL validation blocking private IPs (127.0.0.0/8, 10.0.0.0/8, 169.254.0.0/16, 172.16.0.0/12, 192.168.0.0/16) and metadata endpoints.
- IDOR: Use parameterized queries with ownership check: WHERE id = ? AND user_id = ?
- Container as Root: Add USER node before CMD.
- Debug UI routes/nav: Guard with an admin role check. Do NOT comment out or delete the route.

CRITICAL: Your fix must ELIMINATE the vulnerability, not just add a superficial check. The fix will be reviewed by other AI models — incomplete patches will be rejected.
"""

PATCH_REVIEW_SYSTEM = """
You are a senior security code reviewer.
You will receive: the vulnerability type, the original vulnerable code, and a proposed patch.
RULES:
1. Return ONLY valid JSON: {"approved": true/false, "reason": "one sentence max 30 words"}
2. APPROVE (approved=true) if the patch meaningfully reduces or eliminates the attack surface:
   - SQL Injection: Approve if template literals are replaced with parameterized queries (? placeholders).
   - XSS: Approve if dangerouslySetInnerHTML is removed OR input is escaped/sanitized.
   - Hardcoded Secrets: Approve if literal secrets are replaced with environment variable references (${VAR}).
   - Sensitive Data Exposure: Approve if the debug route is auth-gated (admin/role check). Do NOT approve a patch that merely comments out or deletes the route — that is a suppression, not a fix.
   - SSRF: Approve if URL validation/allowlisting is added.
   - IDOR: Approve if ownership checks or parameterized queries are added.
   - Container as Root: Approve if USER directive is added before CMD.
3. REJECT (approved=false) ONLY if:
   - The patch does NOT address the vulnerability at all (no meaningful change).
   - The patch introduces a WORSE vulnerability than the original.
   - The patch contains placeholder comments instead of real code.
4. Do NOT reject patches for minor style issues, missing error handling, or incomplete edge cases.
   Focus ONLY on whether the core vulnerability is fixed.
"""


def _trim_block(text: str, max_chars: int = 4000) -> str:
    if not text:
        return ""
    s = str(text).strip()
    if len(s) <= max_chars:
        return s
    return s[:max_chars] + "\n... [truncated]"


def _build_patch_prompt(vuln: dict) -> str:
    vuln_name = vuln.get("vuln_name", "Unknown")
    cwe = vuln.get("cwe", "CWE-unknown")
    file_path = vuln.get("file_path", "unknown")
    vulnerable_code = vuln.get("vulnerable_code", "")
    context_snippet = vuln.get("context_snippet", "")
    extraction_quality = vuln.get("extraction_quality", "window")
    imports = vuln.get("imports", "")
    secure_example = vuln.get("secure_example", "")
    kb_strategy = vuln.get("kb_strategy", "")
    kb_anti_patterns = vuln.get("kb_anti_patterns", "")
    related_files = vuln.get("related_files", []) or []
    exploit_payload = vuln.get("exploit_payload", "")

    sections = [
        f"Vulnerability: {vuln_name} ({cwe})",
        f"File: {file_path}",
        "",
        "Vulnerable code:",
        f"```\n{_trim_block(vulnerable_code, 3000)}\n```",
    ]

    if kb_strategy:
        sections.extend([
            "",
            "CWE fix strategy (canonical):",
            f"- {kb_strategy}",
        ])
    if kb_anti_patterns:
        sections.extend([
            "",
            "Avoid these anti-patterns:",
            f"- {_trim_block(kb_anti_patterns, 500)}",
        ])
    if imports:
        sections.extend([
            "",
            "File imports/context:",
            f"```\n{_trim_block(imports, 1000)}\n```",
        ])
    if context_snippet:
        label = "enclosing function" if extraction_quality == "function" else "approximate local window"
        sections.extend([
            "",
            f"Code context ({label}):",
            f"```\n{_trim_block(context_snippet, 2500)}\n```",
        ])
    if secure_example:
        sections.extend([
            "",
            f"In-repo secure reference file: {secure_example}",
        ])
    if related_files:
        sections.extend([
            "",
            f"Related files: {', '.join(related_files[:3])}",
        ])
    if exploit_payload:
        sections.extend([
            "",
            f"Exploit payload observed: {exploit_payload}",
        ])

    # ── Oracle pre-analysis (injected when available) ─────────────────────
    oracle = vuln.get("oracle_analysis") or {}
    if oracle:
        sections.extend(["", "## Oracle Pre-Analysis"])
        if oracle.get("attack_vector"):
            sections.append(f"Attack vector:  {oracle['attack_vector']}")
        if oracle.get("data_flow"):
            sections.append(f"Data flow:      {oracle['data_flow']}")
        if oracle.get("minimal_fix"):
            sections.append(f"Minimal fix:    {oracle['minimal_fix']}")
        avoid = oracle.get("avoid") or []
        if avoid:
            sections.append(f"Avoid:          {'; '.join(avoid[:3])}")

    sections.extend([
        "",
        "Generate the fixed version of the vulnerable code. Return only the replacement snippet in fixed_code.",
    ])
    return "\n".join(sections)


def _build_oracle_prompt(vuln: dict) -> str:
    """Short prompt for the Oracle reasoning step."""
    name = vuln.get("vuln_name", "Unknown")
    cwe  = vuln.get("cwe", "CWE-unknown")
    code = _trim_block(vuln.get("vulnerable_code", ""), 2000)
    ctx  = _trim_block(vuln.get("context_snippet", ""), 1500)
    kb   = vuln.get("kb_strategy", "")
    payload = vuln.get("exploit_payload", "")

    parts = [
        f"Vulnerability: {name} ({cwe})",
        "",
        "Vulnerable code:",
        f"```\n{code}\n```",
    ]
    if ctx:
        parts += ["", "Enclosing context:", f"```\n{ctx}\n```"]
    if kb:
        parts += ["", f"Known fix strategy: {kb}"]
    if payload:
        parts += ["", f"Observed exploit payload: {payload}"]
    parts += ["", "Decompose this vulnerability for the patch agent."]
    return "\n".join(parts)

class PatchCouncil(CouncilOrchestrator):

    async def _oracle_reason(self, model: str, vuln: dict) -> dict:
        """
        Oracle reasoning step: ask the already-loaded patcher model to decompose
        the vulnerability BEFORE generating the patch.

        Uses the same loaded model — no extra VRAM cost.
        Returns a dict with keys: attack_vector, data_flow, minimal_fix, avoid, confidence.
        Returns {} silently on any failure so patch generation still proceeds.
        """
        try:
            oracle_prompt = _build_oracle_prompt(vuln)
            raw = await self._call(model, ORACLE_SYSTEM, oracle_prompt, task_name="Oracle Reasoning")
            # Surface the oracle reasoning for user visibility
            av  = raw.get("attack_vector", "")
            df  = raw.get("data_flow", "")
            mf  = raw.get("minimal_fix", "")
            conf = raw.get("confidence", 0.0)
            thinking = raw.get("thinking", "")
            from rich.table import Table
            from rich.box import SIMPLE
            t = Table(box=SIMPLE, show_header=False, padding=(0, 1))
            t.add_column("k", style="dim cyan", no_wrap=True)
            t.add_column("v", style="white")
            if thinking: t.add_row("thinking",      thinking[:120])
            if av:       t.add_row("attack_vector", av[:120])
            if df:       t.add_row("data_flow",     df[:120])
            if mf:       t.add_row("minimal_fix",   mf[:160])
            avoid = raw.get("avoid") or []
            if avoid:    t.add_row("avoid",         "; ".join(avoid[:2])[:120])
            t.add_row("confidence", f"{conf:.2f}")
            console.print(Panel(t, title=f"[yellow bold]⚙ Oracle Analysis[/yellow bold]  [dim]{vuln.get('vuln_name','')}[/dim]", border_style="yellow"))
            return raw
        except Exception:
            return {}

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
        reviewer_models = selector.get_reviewers(count=2)

        console.print(f"[dim]  Patcher:   {patch_model}[/dim]")
        console.print(f"[dim]  Reviewers: {', '.join(reviewer_models)}[/dim]")

        # Stage 1: Unload everything, load patcher
        for model in list(self.vram.loaded.keys()):
            await self.vram.unload(model)

        try:
            await self.vram.ensure_loaded(patch_model)
        except Exception:
            # Fallback to any available model THAT ISN'T the one that just failed
            fallback_candidates = [m for m in selector.models if m.name != patch_model]
            if fallback_candidates:
                patch_model = fallback_candidates[0].name
            elif selector.models:
                patch_model = selector.models[0].name  # Only option
            else:
                return {"fixed_code": "", "patch_safety": "rejected",
                        "unsafe_reason": "No models available", "dissent_reasons": ["No Ollama models"]}
            console.print(f"[yellow]⚠ Patcher failed. Using {patch_model}.[/yellow]")
            try:
                await self.vram.ensure_loaded(patch_model)
            except Exception:
                return {"fixed_code": "", "patch_safety": "rejected",
                        "unsafe_reason": "No models available", "dissent_reasons": ["All models failed to load"]}

        vuln_dict = {
            "vuln_name": vuln_name,
            "cwe": cwe,
            "file_path": file_path,
            "vulnerable_code": vulnerable_code,
        }

        # ── Oracle: decompose before generating ──
        console.print(f"[dim]Stage 0: Oracle reasoning ({patch_model})...[/dim]")
        oracle = await self._oracle_reason(patch_model, vuln_dict)
        if oracle:
            vuln_dict["oracle_analysis"] = oracle

        patch_prompt = _build_patch_prompt(vuln_dict)

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
        # FIX: Use .get() instead of hard key access to prevent KeyError
        dissent_reasons = [a.get("reason", "No reason provided") for a in approvals if not a.get("approved", False)]

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
        Agent-Centric Batching with Patch Cache:
        - Loads each model ONCE and processes ALL vulnerabilities before swapping.
        - Stage 1 patches are CACHED so they survive review-stage crashes.
        - If reviews crash, cached patches are returned with 'review_needed' status
          instead of being thrown away and regenerated from scratch.

        vuln_list: list of dicts with keys: vuln_name, cwe, vulnerable_code, file_path
        Returns: list of patch result dicts (same format as generate_and_validate_patch)
        """
        if not vuln_list:
            return []

        console.print(f"\n[bold magenta]═══ Batch Patch Mode: {len(vuln_list)} vulnerabilities ═══[/bold magenta]")

        # Discover models — uses intelligent resource-aware brain
        selector = await get_selector(quiet=True)
        self.vram.update_costs(selector.get_vram_costs())
        patch_model = selector.get("patcher")
        reviewer_models = selector.get_reviewers(count=2)  # Resource-aware: returns 1 or 2

        console.print(f"[dim]  Patcher:   {patch_model}[/dim]")
        console.print(f"[dim]  Reviewers: {', '.join(reviewer_models)} ({selector.strategy})[/dim]")

        # ── Stage 1: Load patcher ONCE, generate ALL patches ──
        console.print(f"\n[bold cyan]Stage 1/3: Generating {len(vuln_list)} patches ({patch_model})[/bold cyan]")
        for model in list(self.vram.loaded.keys()):
            await self.vram.unload(model)

        try:
            await self.vram.ensure_loaded(patch_model)
        except Exception:
            # Fallback to any available model THAT ISN'T the one that just failed
            fallback_candidates = [m for m in selector.models if m.name != patch_model]
            if fallback_candidates:
                patch_model = fallback_candidates[0].name
            elif selector.models:
                patch_model = selector.models[0].name  # Only option
            else:
                return [{"fixed_code": "", "patch_safety": "rejected",
                         "unsafe_reason": "No models available"} for _ in vuln_list]
            console.print(f"[yellow]⚠ Patcher failed. Using {patch_model}.[/yellow]")
            try:
                await self.vram.ensure_loaded(patch_model)
            except Exception:
                return [{"fixed_code": "", "patch_safety": "rejected",
                         "unsafe_reason": "All models failed to load"} for _ in vuln_list]

        # ── PATCH CACHE: these results survive even if reviews crash ──
        patch_results = []
        for i, v in enumerate(vuln_list, 1):
            console.print(f"  [dim][{i}/{len(vuln_list)}] Patching:[/dim] [cyan]{v['vuln_name']}[/cyan]")
            # ── Oracle: decompose the problem before generating the patch ──
            oracle = await self._oracle_reason(patch_model, v)
            if oracle:
                v = dict(v)  # don't mutate the caller's dict
                v["oracle_analysis"] = oracle
            prompt = _build_patch_prompt(v)
            try:
                result = await self._call(patch_model, PATCH_GENERATION_SYSTEM, prompt, task_name="Patch Generation")
                patch_results.append(result)
            except Exception as e:
                console.print(f"[red]  Error: {e}[/red]")
                patch_results.append({"fixed_code": "", "unsafe_reason": "Generation failed"})

        # ── Stage 2 & 3: Reviews — PARALLEL if hardware allows, sequential otherwise ──
        # This is wrapped in try/except so review crashes DON'T lose Stage 1 patches
        await self.vram.unload(patch_model)

        all_approvals = [[] for _ in vuln_list]  # per-vuln approval lists
        review_completed = False

        # Use the selector's strategy decision — no redundant VRAM checks
        unique_reviewers = list(dict.fromkeys(reviewer_models))  # deduplicate, preserve order
        can_parallel = (
            len(unique_reviewers) >= 2
            and selector.parallel_review_enabled
        )

        try:
            if can_parallel:
                # ── PARALLEL REVIEW: Both reviewers loaded at once ──
                console.print(f"\n[bold cyan]Stage 2/2: Parallel review — {' & '.join(unique_reviewers[:2])} (both loaded)[/bold cyan]")
                console.print(f"[dim]  ⚡ Parallel mode: {self.vram.VRAM_LIMIT:.0f}GB VRAM budget allows dual-model execution[/dim]")

                # Load both reviewers simultaneously
                await self.vram.ensure_loaded_together(unique_reviewers[:2])

                # For each vulnerability, run BOTH reviews concurrently
                for i, (v, patch_res) in enumerate(zip(vuln_list, patch_results)):
                    fixed_code = patch_res.get("fixed_code", "")
                    if not fixed_code:
                        for reviewer in unique_reviewers[:2]:
                            all_approvals[i].append({"model": reviewer, "approved": False, "reason": "No code to review"})
                        continue

                    review_prompt = (
                        f"Vulnerability: {v['vuln_name']} ({v['cwe']})\n\n"
                        f"Original vulnerable code:\n```\n{v['vulnerable_code']}\n```\n\n"
                        f"Proposed patch:\n```\n{fixed_code}\n```"
                    )

                    # Fire both reviews simultaneously with asyncio.gather
                    async def _review_one(reviewer_model, prompt):
                        try:
                            review = await self._call(
                                reviewer_model, PATCH_REVIEW_SYSTEM, prompt,
                                task_name=f"Parallel Review ({reviewer_model})"
                            )
                            return {"model": reviewer_model, **review}
                        except Exception as e:
                            return {"model": reviewer_model, "approved": False, "reason": f"Error: {str(e)[:40]}"}

                    import asyncio
                    results = await asyncio.gather(
                        _review_one(unique_reviewers[0], review_prompt),
                        _review_one(unique_reviewers[1], review_prompt),
                    )
                    for r in results:
                        all_approvals[i].append(r)

                # Unload both reviewers
                for reviewer in unique_reviewers[:2]:
                    await self.vram.unload(reviewer)

            else:
                # ── SEQUENTIAL REVIEW: One reviewer at a time (original flow) ──
                for r_idx, reviewer in enumerate(unique_reviewers, 2):
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

            review_completed = True

        except Exception as review_error:
            console.print(f"[yellow]⚠ Review stage error: {str(review_error)[:80]}[/yellow]")
            console.print(f"[cyan]  → Using cached patches from Stage 1 (no regeneration needed)[/cyan]")

        # ── Assemble final results ──
        final_results = []
        for i, patch_res in enumerate(patch_results):
            approvals = all_approvals[i] if i < len(all_approvals) else []

            # Safe key access — use .get() to prevent KeyError on missing 'reason'
            approved_count = sum(1 for a in approvals if a.get("approved", False))
            total_reviewers = len(approvals)
            dissent_reasons = [a.get("reason", "No reason provided") for a in approvals if not a.get("approved", False)]

            fixed_code = patch_res.get("fixed_code", "")

            if not fixed_code:
                final_safety = "rejected"
            elif not review_completed and total_reviewers == 0:
                final_safety = "review_needed"
            elif approved_count == total_reviewers and total_reviewers > 0:
                final_safety = "safe"
            elif approved_count >= 1:
                final_safety = "review_needed"
            elif total_reviewers == 0:
                final_safety = "review_needed"
            else:
                final_safety = "rejected"

            final_results.append({
                "fixed_code": fixed_code,
                "unsafe_reason": patch_res.get("unsafe_reason", ""),
                "patch_safety": final_safety,
                "approvals": approvals,
                "dissent_reasons": dissent_reasons,
                "vote_summary": f"{approved_count}/{total_reviewers} validators approved" if total_reviewers > 0 else "Unreviewed (cached from Stage 1)"
            })

        mode_label = "parallel" if can_parallel else "sequential"
        console.print(f"\n[bold green]═══ Batch complete: {len(final_results)} patches ({mode_label} review) ═══[/bold green]")
        return final_results
