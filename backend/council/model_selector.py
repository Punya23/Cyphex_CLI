"""
CYPHEX — Dynamic Model Selector (Zero-Config)

Automatically discovers locally installed Ollama models and assigns
the best available model to each Council role based on:
  1. Parameter size (larger = more capable)
  2. Specialization (coding models preferred for code tasks)
  3. Available system resources

Roles:
  - detector:   Finds vulnerabilities in code (prefers coding models)
  - validator:  Cross-checks findings for false positives
  - narrator:   Writes the final security report
  - patcher:    Generates code patches (prefers coding models)

Usage:
    selector = ModelSelector()
    await selector.discover()  # one-time probe
    model = selector.get("detector")  # best model for this role
"""

import re
import httpx
import asyncio
from typing import Optional
from rich.console import Console

console = Console()

OLLAMA_BASE = "http://localhost:11434"

# ── Model classification patterns ──────────────────────────────
# Models matching these patterns are considered "code-aware"
CODE_MODEL_PATTERNS = [
    r"coder", r"codellama", r"code", r"starcoder", r"deepseek-coder",
    r"wizard-?coder", r"phind", r"magicoder", r"codestral", r"qwen.*coder",
    r"granite-code", r"cyphex-patch",
]

# Models matching these are strong general-purpose reasoners
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


class ModelSelector:
    """
    Zero-config model selector. Discovers installed Ollama models and
    assigns the best one to each role.

    Role priority:
      detector  → largest code model, else largest general model
      validator → second-largest model (diversity for debate)
      narrator  → largest general model (report writing)
      patcher   → largest code model, else largest general model
    """

    ROLES = ("detector", "validator", "narrator", "patcher")

    def __init__(self):
        self.models: list[ModelInfo] = []
        self.assignments: dict[str, str] = {}  # role → model name
        self._discovered = False

    async def discover(self, quiet: bool = False) -> bool:
        """
        Query Ollama for installed models and build assignments.
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

        # Assign roles
        self._assign_roles()
        self._discovered = True

        if not quiet:
            console.print(f"\n  [bold cyan]⚡ Model Discovery[/bold cyan]  "
                          f"Found {len(self.models)} Ollama model(s)")
            for role, model_name in self.assignments.items():
                info = next((m for m in self.models if m.name == model_name), None)
                size_tag = f"{info.param_size}B" if info else "?"
                code_tag = " [code]" if info and info.is_code else ""
                console.print(f"    {role:12s} → {model_name} ({size_tag}{code_tag})")
            console.print()

        return True

    def _assign_roles(self):
        """Assign the best available model to each role."""
        if not self.models:
            return

        # Separate code and general models
        code_models = [m for m in self.models if m.is_code]
        general_models = [m for m in self.models if not m.is_code]
        all_sorted = self.models  # already sorted by size desc

        # Helper: pick best from a list, with fallback
        def best(preferred: list[ModelInfo], fallback: list[ModelInfo]) -> str:
            if preferred:
                return preferred[0].name
            if fallback:
                return fallback[0].name
            return all_sorted[0].name

        # detector: prefers code models (understanding vuln code)
        self.assignments["detector"] = best(code_models, general_models)

        # patcher: prefers code models (generating fix code)
        self.assignments["patcher"] = best(code_models, general_models)

        # narrator: prefers general models (writing reports)
        self.assignments["narrator"] = best(general_models, code_models)

        # validator: pick the SECOND best model for debate diversity
        # If we only have 1 model, reuse it
        if len(all_sorted) >= 2:
            # Pick a model different from detector for diversity
            detector_name = self.assignments["detector"]
            for m in all_sorted:
                if m.name != detector_name:
                    self.assignments["validator"] = m.name
                    break
            else:
                self.assignments["validator"] = all_sorted[0].name
        else:
            self.assignments["validator"] = all_sorted[0].name

    def get(self, role: str) -> str:
        """Get the model name assigned to a role. Falls back to first available."""
        if role in self.assignments:
            return self.assignments[role]
        if self.models:
            return self.models[0].name
        raise RuntimeError("No Ollama models available. Run: ollama pull phi3:mini")

    def get_validators(self, count: int = 3) -> list[str]:
        """
        Get a list of models for the Council debate (false-positive filtering).
        Uses up to `count` distinct models for diversity. If fewer models exist,
        duplicates the best one to fill.
        """
        if not self.models:
            raise RuntimeError("No Ollama models available. Run: ollama pull phi3:mini")

        # Use distinct models, prioritizing code models first
        names = []
        seen = set()
        # Code models first, then general, all sorted by size
        for m in sorted(self.models, key=lambda x: (not x.is_code, -x.param_size)):
            if m.name not in seen:
                names.append(m.name)
                seen.add(m.name)
            if len(names) >= count:
                break

        # Fill remaining slots with the best model
        while len(names) < count:
            names.append(self.models[0].name)

        return names

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
