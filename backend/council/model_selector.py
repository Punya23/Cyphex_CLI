"""
CYPHEX — Intelligent Model Selector (Resource-Aware Brain)

Automatically discovers locally installed Ollama models and builds an
OPTIMAL execution strategy based on actual hardware resources.

Philosophy:
  - QUALITY FIRST: Always prefer the largest, most capable model
  - SMART PARALLELISM: Only run 2+ models simultaneously when VRAM allows
    AND it actually improves quality (don't force diversity at the cost of speed)
  - ADAPTIVE ROLES: A large general model (llama3.1:8b) IS better at code
    than a small code model (deepseek-coder:1.3b). Don't blindly prefer "code" tags.

Quality Score = param_size * (1.15 if code_specialist else 1.0)
  → A 7B code model scores 8.05, but an 8B general model scores 8.0
  → They're essentially tied — the system picks the best for each task type

Execution Strategies:
  - SOLO_POWERHOUSE: One large model does everything (limited VRAM)
  - DUAL_SPECIALIST: Two models split work (moderate VRAM)
  - FULL_COUNCIL: 3+ models for parallel debate + review (high VRAM)
"""

import re
import httpx
import asyncio
from typing import Optional
from rich.console import Console

console = Console()

OLLAMA_BASE = "http://localhost:11434"

# ── Model classification patterns ──────────────────────────────
CODE_MODEL_PATTERNS = [
    r"coder", r"codellama", r"starcoder", r"deepseek-coder",
    r"wizard-?coder", r"phind", r"magicoder", r"codestral", r"qwen.*coder",
    r"granite-code", r"cyphex-patch",
]

REASONING_MODEL_PATTERNS = [
    r"llama", r"phi", r"mistral", r"mixtral", r"gemma", r"qwen",
    r"command-r", r"vicuna", r"neural-chat", r"yi-", r"solar",
    r"deepseek-r1", r"deepseek-v",
]


def _extract_param_size(model_name: str, model_size_bytes: int = 0) -> float:
    """
    Extract parameter count in billions from model name or file size.

    Examples:
        "llama3.2:70b"        → 70.0
        "deepseek-coder:33b"  → 33.0
        "phi3:mini"           → 3.8  (estimated from file size)
        "qwen2.5-coder:7b"   → 7.0
    """
    # Try to extract from tag (e.g., ":70b", ":7b", ":1.3b", ":0.5b")
    match = re.search(r":.*?(\d+\.?\d*)b", model_name.lower())
    if match:
        return float(match.group(1))

    # Try from the model name itself (e.g., "llama3.1-70b-instruct")
    match = re.search(r"(\d+\.?\d*)b", model_name.lower())
    if match:
        val = float(match.group(1))
        if val >= 0.1:  # Avoid matching version numbers like "3.2"
            return val

    # Estimate from file size (rough: 1B params ≈ 0.6 GB quantized)
    if model_size_bytes > 0:
        estimated = round(model_size_bytes / (0.6 * 1e9), 1)
        return max(estimated, 0.5)

    # Known small models
    name_lower = model_name.lower()
    if "mini" in name_lower:
        return 3.8
    if "tiny" in name_lower:
        return 1.0
    if "small" in name_lower:
        return 2.0
    if "medium" in name_lower:
        return 7.0
    if "large" in name_lower:
        return 13.0

    return 1.0  # Unknown — assume small


def _is_code_model(name: str) -> bool:
    """Check if a model is specialized for code tasks."""
    name_lower = name.lower()
    return any(re.search(p, name_lower) for p in CODE_MODEL_PATTERNS)


def _vram_estimate(param_billions: float) -> float:
    """Estimate VRAM usage in GB for a quantized model."""
    # Rough heuristic: Q4 quantized ≈ 0.6 GB per billion params + 0.3 GB overhead
    return round(param_billions * 0.6 + 0.3, 1)


def _quality_score(model: 'ModelInfo', task: str = "general") -> float:
    """
    Compute a quality heuristic for a model on a given task.
    
    The key insight: param_size is the PRIMARY driver of quality.
    Code specialization gives a modest bonus, NOT an override.
    
    An 8B general model > 7B code model for MOST tasks including code,
    because the larger parameter count gives better reasoning.
    The code model only wins when tasks are pure code-generation.
    """
    base = model.param_size

    if task in ("patcher", "detector"):
        # Code tasks: code models get 15% bonus
        if model.is_code:
            return base * 1.15
        return base
    elif task == "narrator":
        # Report writing: general models get 10% bonus
        if not model.is_code:
            return base * 1.10
        return base
    else:
        # Validator/debate: raw capability matters most
        return base


class ModelInfo:
    """Metadata for a discovered Ollama model."""
    __slots__ = ("name", "param_size", "is_code", "vram_gb", "raw_size")

    def __init__(self, name: str, param_size: float, is_code: bool,
                 vram_gb: float, raw_size: int = 0):
        self.name = name
        self.param_size = param_size
        self.is_code = is_code
        self.vram_gb = vram_gb
        self.raw_size = raw_size

    def __repr__(self):
        tag = " [CODE]" if self.is_code else ""
        return f"{self.name} ({self.param_size}B, ~{self.vram_gb}GB VRAM){tag}"


# ── Execution Strategies ──────────────────────────────────────
STRATEGY_SOLO = "SOLO_POWERHOUSE"      # 1 model does everything
STRATEGY_DUAL = "DUAL_SPECIALIST"      # 2 models, smart split
STRATEGY_FULL = "FULL_COUNCIL"         # 3+ models, full debate


class ModelSelector:
    """
    Resource-aware model brain. Discovers models, measures hardware,
    and builds the optimal execution strategy.

    Instead of blindly assigning "code model → patcher", it:
      1. Scores every model for every task using quality_score()
      2. Picks the BEST model per task (could be general or code)
      3. Determines parallelism strategy from actual VRAM budget
      4. Never forces 2 models when 1 bigger model is better
    """

    ROLES = ("detector", "validator", "narrator", "patcher")

    def __init__(self):
        self.models: list[ModelInfo] = []
        self.assignments: dict[str, str] = {}   # role → model name
        self._discovered = False
        self.strategy: str = STRATEGY_SOLO
        self.vram_budget: float = 0.0           # Usable VRAM in GB
        self._execution_plan: dict = {}         # Strategy details

    async def discover(self, quiet: bool = False) -> bool:
        """
        Query Ollama for installed models and build the optimal strategy.
        Returns True if at least one model is available.
        """
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                r = await client.get(f"{OLLAMA_BASE}/api/tags")
                data = r.json()
        except Exception:
            if not quiet:
                console.print("[yellow]⚠ Ollama not reachable at localhost:11434[/yellow]")
            return False

        raw_models = data.get("models", [])
        if not raw_models:
            if not quiet:
                console.print("[yellow]⚠ No Ollama models installed[/yellow]")
            return False

        # Build model info list
        self.models = []
        for m in raw_models:
            name = m.get("name", "")
            size_bytes = m.get("size", 0)
            param_size = _extract_param_size(name, size_bytes)
            is_code = _is_code_model(name)
            vram = _vram_estimate(param_size)
            self.models.append(ModelInfo(name, param_size, is_code, vram, size_bytes))

        # Sort by param size descending (biggest first)
        self.models.sort(key=lambda m: m.param_size, reverse=True)

        # Detect VRAM budget
        try:
            from cyphex.hardware import get_gpu_info
            info = get_gpu_info()
            raw_vram = info.get("vram_gb", 0)
            self.vram_budget = max(raw_vram - 2.0, 4.0) if raw_vram > 0 else 5.5
        except Exception:
            self.vram_budget = 5.5

        # Build intelligent strategy
        self._build_strategy()
        self._discovered = True

        if not quiet:
            console.print(f"\n  [bold cyan]⚡ Model Brain[/bold cyan]  "
                          f"Found {len(self.models)} model(s) | "
                          f"VRAM budget: {self.vram_budget:.1f}GB | "
                          f"Strategy: [bold]{self.strategy}[/bold]")
            for role, model_name in self.assignments.items():
                info = next((m for m in self.models if m.name == model_name), None)
                size_tag = f"{info.param_size}B" if info else "?"
                code_tag = " [code]" if info and info.is_code else ""
                score = _quality_score(info, role) if info else 0
                console.print(f"    {role:12s} → {model_name} ({size_tag}{code_tag}) "
                              f"[dim]quality={score:.1f}[/dim]")
            console.print()

        return True

    def _build_strategy(self):
        """
        The Brain: determines optimal model assignments AND execution strategy
        based on actual models + actual VRAM.
        """
        if not self.models:
            return

        n_models = len(self.models)

        # ── Step 1: Score every model for every role ──
        # For each role, rank models by quality score
        role_rankings: dict[str, list[tuple[float, ModelInfo]]] = {}
        for role in self.ROLES:
            scored = [(round(_quality_score(m, role), 2), m) for m in self.models]
            scored.sort(key=lambda x: x[0], reverse=True)
            role_rankings[role] = scored

        # ── Step 2: Assign best model per role ──
        for role in self.ROLES:
            self.assignments[role] = role_rankings[role][0][1].name

        # ── Step 3: Determine parallelism strategy ──
        # Key question: can we actually benefit from multiple models?

        largest = self.models[0]
        total_all_models_vram = sum(m.vram_gb for m in self.models)

        if n_models == 1:
            # Only one model — solo powerhouse, no choice
            self.strategy = STRATEGY_SOLO
            self._execution_plan = {
                "reason": f"Single model available: {largest.name}",
                "parallel_review": False,
                "debate_models": 1,
                "review_models": 1,
            }
        elif n_models == 2:
            # Two models — check if both fit simultaneously
            can_parallel = (self.models[0].vram_gb + self.models[1].vram_gb) <= self.vram_budget
            if can_parallel:
                self.strategy = STRATEGY_DUAL
                self._execution_plan = {
                    "reason": f"2 models fit in VRAM ({self.models[0].vram_gb + self.models[1].vram_gb:.1f}GB / {self.vram_budget:.1f}GB)",
                    "parallel_review": True,
                    "debate_models": 2,
                    "review_models": 2,
                }
            else:
                # Can't fit both — use the BIGGER one for patching, smaller for review
                self.strategy = STRATEGY_DUAL
                self._execution_plan = {
                    "reason": f"2 models available but sequential (VRAM: {self.vram_budget:.1f}GB)",
                    "parallel_review": False,
                    "debate_models": 2,
                    "review_models": 2,
                }
        else:
            # 3+ models — check what fits for parallel execution
            # Try fitting as many as possible for debate
            fit_count = 0
            fit_vram = 0.0
            for m in self.models:
                if fit_vram + m.vram_gb <= self.vram_budget:
                    fit_count += 1
                    fit_vram += m.vram_gb
                else:
                    break

            if fit_count >= 3:
                self.strategy = STRATEGY_FULL
                self._execution_plan = {
                    "reason": f"Full council: {fit_count} models fit simultaneously ({fit_vram:.1f}GB)",
                    "parallel_review": True,
                    "debate_models": min(fit_count, n_models),
                    "review_models": min(fit_count, n_models),
                }
            elif fit_count >= 2:
                self.strategy = STRATEGY_DUAL
                self._execution_plan = {
                    "reason": f"Dual parallel: 2 models fit ({fit_vram:.1f}GB), 3rd sequential",
                    "parallel_review": True,
                    "debate_models": n_models,
                    "review_models": 2,
                }
            else:
                # Even 2 models don't fit — use biggest for everything, others sequential
                self.strategy = STRATEGY_SOLO
                self._execution_plan = {
                    "reason": f"VRAM too tight ({self.vram_budget:.1f}GB) for parallel — using {largest.name} as primary",
                    "parallel_review": False,
                    "debate_models": n_models,
                    "review_models": 1,
                }

        # ── Step 4: Optimize validator assignment for diversity ──
        # Validator should differ from detector for debate diversity (if possible)
        if n_models >= 2:
            detector_name = self.assignments["detector"]
            # Pick the highest-quality model that ISN'T the detector
            for score, m in role_rankings["validator"]:
                if m.name != detector_name:
                    self.assignments["validator"] = m.name
                    break

    def get(self, role: str) -> str:
        """Get the model name assigned to a role. Falls back to first available."""
        if role in self.assignments:
            return self.assignments[role]
        if self.models:
            return self.models[0].name
        raise RuntimeError("No Ollama models available. Run: ollama pull phi3:mini")

    def get_validators(self, count: int = 3) -> list[str]:
        """
        Get models for council debate. INTELLIGENT selection:
        - Returns only as many DISTINCT models as make sense for the VRAM budget
        - Never pads with duplicates just to hit a count — that wastes compute
        - If only 1 model fits at a time, returns 1 (not 3 copies of it)
        """
        if not self.models:
            raise RuntimeError("No Ollama models available. Run: ollama pull phi3:mini")

        # How many distinct models should we actually use?
        max_useful = self._execution_plan.get("debate_models", len(self.models))
        actual_count = min(count, max_useful, len(self.models))

        # Score all models for validation quality
        scored = sorted(
            self.models,
            key=lambda m: _quality_score(m, "validator"),
            reverse=True
        )

        names = []
        seen = set()
        for m in scored:
            if m.name not in seen:
                names.append(m.name)
                seen.add(m.name)
            if len(names) >= actual_count:
                break

        # Only pad if we literally have no models (shouldn't happen)
        if not names and self.models:
            names = [self.models[0].name]

        return names

    def get_reviewers(self, count: int = 2) -> list[str]:
        """
        Get models for patch review. Resource-aware:
        - If VRAM allows parallel review, returns 2 distinct models
        - If VRAM is tight, returns just the 1 best model (no wasted sequential re-runs)
        """
        if not self.models:
            raise RuntimeError("No Ollama models available. Run: ollama pull phi3:mini")

        max_reviewers = self._execution_plan.get("review_models", 1)
        actual_count = min(count, max_reviewers, len(self.models))

        # For reviews, prefer code-aware models (they understand patches better)
        scored = sorted(
            self.models,
            key=lambda m: _quality_score(m, "patcher"),
            reverse=True
        )

        names = []
        seen = set()
        for m in scored:
            if m.name not in seen:
                names.append(m.name)
                seen.add(m.name)
            if len(names) >= actual_count:
                break

        return names if names else [self.models[0].name]

    @property
    def parallel_review_enabled(self) -> bool:
        """Whether the strategy allows parallel model execution for reviews."""
        return self._execution_plan.get("parallel_review", False)

    def get_vram_costs(self) -> dict[str, float]:
        """Return a dynamic VRAM cost table for all discovered models."""
        return {m.name: m.vram_gb for m in self.models}

    @property
    def available(self) -> bool:
        return self._discovered and len(self.models) > 0

    def summary_table(self) -> list[tuple[str, str, float, bool]]:
        """Return (name, role, param_size, is_code) for display."""
        role_map = {v: k for k, v in self.assignments.items()}
        rows = []
        for m in self.models:
            role = role_map.get(m.name, "—")
            rows.append((m.name, role, m.param_size, m.is_code))
        return rows


# ── Singleton for process-wide reuse ──────────────────────────
_global_selector: Optional[ModelSelector] = None


async def get_selector(quiet: bool = False) -> ModelSelector:
    """Get or create the global ModelSelector singleton."""
    global _global_selector
    if _global_selector is None or not _global_selector.available:
        _global_selector = ModelSelector()
        await _global_selector.discover(quiet=quiet)
    return _global_selector
