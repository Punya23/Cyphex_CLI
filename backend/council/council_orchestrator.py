import httpx
import json
import re
import asyncio
from typing import Optional
from rich.console import Console
from rich.panel import Panel
from rich.live import Live
from backend.council.council_errors import CouncilCallError, ModelNotFoundError

OLLAMA_BASE = "http://localhost:11434"
console = Console()

class VRAMManager:
    """
    Tracks which models are currently loaded and enforces VRAM budget.
    VRAM costs are dynamically populated by ModelSelector; unknown models
    are estimated at ~2.0 GB.
    """

    # Seed costs for known models (overridden by ModelSelector at runtime)
    VRAM_COST = {
        "deepseek-coder:1.3b": 1.0,
        "phi3:mini":            2.2,
        "llama3.2:1b":          1.0,
        "cyphex-patch":         4.5,
        "qwen2.5-coder:7b":    4.5,
        "qwen2.5-coder:3b":    2.0,
    }

    VRAM_LIMIT = 5.5  # GB — leave 0.5 GB for OS/driver overhead

    def __init__(self):
        self.loaded: dict[str, float] = {}  # model → VRAM cost

    def update_costs(self, dynamic_costs: dict[str, float]):
        """Merge dynamically discovered VRAM costs (from ModelSelector)."""
        self.VRAM_COST.update(dynamic_costs)

    def can_load(self, model: str) -> bool:
        cost = self.VRAM_COST.get(model, 2.0)
        return sum(self.loaded.values()) + cost <= self.VRAM_LIMIT

    async def ensure_loaded(self, model: str):
        if model in self.loaded:
            return
        # If adding this model would exceed budget, unload least-recently-used
        cost = self.VRAM_COST.get(model, 2.0)
        while sum(self.loaded.values()) + cost > self.VRAM_LIMIT and self.loaded:
            evict = next(iter(self.loaded))
            await self.unload(evict)
        # Warm up the model with a no-op prompt
        try:
            await self._raw_call(model, "ready", stream=False)
            self.loaded[model] = cost
        except Exception as e:
            raise ModelNotFoundError(f"Could not load model {model}: {e}")

    async def unload(self, model: str):
        """Force Ollama to release VRAM for this model immediately."""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                await client.post(
                    f"{OLLAMA_BASE}/api/generate",
                    json={"model": model, "prompt": "", "keep_alive": 0}
                )
        except Exception:
            pass
        self.loaded.pop(model, None)

    async def _raw_call(self, model: str, prompt: str, stream: bool = False) -> str:
        async with httpx.AsyncClient(timeout=None) as client:
            r = await client.post(
                f"{OLLAMA_BASE}/api/generate",
                json={
                    "model": model,
                    "prompt": prompt,
                    "stream": stream,
                    "keep_alive": "10m",
                    "options": {"temperature": 0.1, "top_p": 0.9, "num_ctx": 4096}
                }
            )
            return r.json()["response"]


class CouncilOrchestrator:

    UNIVERSAL_ANTI_HALLUCINATION_RULES = """
ANTI-HALLUCINATION RULES — apply on every response:
1. Never invent CVE IDs. Never write "CVE-" followed by any number.
   If asked about CVE, respond: "I cannot assign a CVE without NVD verification."
2. Use only these CWE numbers (hardcoded):
   CWE-89 (SQLi), CWE-79 (XSS), CWE-78 (CMDi), CWE-22 (Path Traversal/LFI),
   CWE-798 (Hardcoded Secret), CWE-306 (Missing Auth), CWE-942 (CORS),
   CWE-614 (Insecure Cookie), CWE-693 (Missing Header), CWE-1104 (Supply Chain)
   If the vulnerability type is not in this list, use "CWE-unknown".
3. Never use phrases like "might be", "could potentially", "appears to be",
   "seems vulnerable". Every finding statement must be backed by evidence.
4. If you are uncertain, set confirmed=false or approved=false. Never guess true.
5. You MUST provide your detailed, step-by-step reasoning in a "thinking" key inside the final JSON object BEFORE the decision keys. This is mandatory for transparency and strong reasoning.
6. Return ONLY valid JSON. No preamble, no markdown.
"""

    def __init__(self):
        self.vram = VRAMManager()

    async def _call(self, model: str, system: str, prompt: str, task_name: str = "Reasoning") -> dict:
        """
        Call a model and return parsed JSON.
        Handles: model loading, JSON extraction from markdown fences, retries.
        Raises CouncilCallError if model returns non-JSON after 2 retries.
        """
        console.print(f"[dim]VRAM Manager: Loading {model}...[/dim]")
        await self.vram.ensure_loaded(model)

        full_system = f"{system}\n\n{self.UNIVERSAL_ANTI_HALLUCINATION_RULES}"

        for attempt in range(2):
            try:
                # Use Live to show thinking process — 90s timeout prevents infinite hangs
                with Live(Panel(f"[cyan bold]Evaluating[/cyan bold]\n[dim]Model: {model}[/dim]\n[yellow]Status: Thinking...[/yellow]", border_style="cyan"), refresh_per_second=2, console=console, transient=True) as live:
                    async with httpx.AsyncClient(timeout=httpx.Timeout(90.0, connect=10.0)) as client:
                        r = await client.post(
                            f"{OLLAMA_BASE}/api/chat",
                            json={
                                "model": model,
                                "messages": [
                                    {"role": "system", "content": full_system},
                                    {"role": "user", "content": prompt},
                                ],
                                "stream": False,
                                "format": "json",
                                "keep_alive": "10m",
                                "options": {
                                    "temperature": 0.1,
                                    "top_p": 0.9,
                                    "num_predict": 512,   # Cap response length — prevents rambling
                                    "num_ctx": 2048,      # Smaller context = faster inference
                                }
                            }
                        )
                    raw = r.json()["message"]["content"]
                    live.update(Panel(f"[green bold]✓ Done[/green bold] [dim]({model})[/dim]", border_style="green"))

                # Strip markdown code fences just in case
                clean = re.sub(r"```(?:json)?|```", "", raw).strip()
                
                try:
                    parsed = json.loads(clean)
                except json.JSONDecodeError:
                    # Fallback to regex extraction
                    match = re.search(r'(\{.*\}|\[.*\])', clean, re.DOTALL)
                    if match:
                        parsed = json.loads(match.group(1))
                    else:
                        raise json.JSONDecodeError("No JSON structure found", clean, 0)
                
                # Extract and display thinking from the JSON
                if isinstance(parsed, dict) and "thinking" in parsed:
                    thinking_content = str(parsed["thinking"]).strip()
                    if thinking_content:
                        console.print(Panel(thinking_content, title=f"[{model}] Thinking Process", border_style="blue"))
                    
                # Display the decision if applicable
                if isinstance(parsed, dict):
                    if "confirmed" in parsed:
                        c = "green" if parsed["confirmed"] else "red"
                        console.print(f"  └─ [{c}]{model} vote: {parsed['confirmed']}[/{c}] - {parsed.get('reason', '')}")
                    elif "approved" in parsed:
                        c = "green" if parsed["approved"] else "red"
                        console.print(f"  └─ [{c}]{model} review: {parsed['approved']}[/{c}] - {parsed.get('reason', '')}")
                
                return parsed
            except json.JSONDecodeError:
                if attempt == 1:
                    raise CouncilCallError(f"{model} returned non-JSON after 2 attempts: {raw[:200]}")
                console.print(f"[yellow]⚠ {model} returned invalid JSON, retrying...[/yellow]")
                continue
            except Exception as e:
                raise CouncilCallError(f"{model} API error: {str(e)}")

        raise CouncilCallError(f"{model} failed after 2 attempts")
