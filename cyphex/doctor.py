"""
CYPHEX Doctor — System health check and setup assistant.

Verifies all dependencies are present and recommends the right
configuration based on the user's hardware.

Usage:
    cyphex doctor
"""

import os
import sys
import shutil
import asyncio
import subprocess
import platform
from typing import Optional

from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from cyphex.hardware import get_gpu_info, detect_mode, MODE_DESCRIPTIONS, MODE_MODELS

console = Console()


def _check_binary(name: str) -> tuple[bool, str]:
    """Check if a binary is available and return its version."""
    if name == "semgrep" and os.name == "nt":
        try:
            result = subprocess.run(
                ["wsl", "semgrep", "--version"], capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                version = result.stdout.strip().split("\n")[0]
                return True, version
        except Exception:
            pass

    path = shutil.which(name)
    if not path:
        return False, "not installed"
    try:
        result = subprocess.run(
            [path, "--version"], capture_output=True, text=True, timeout=5
        )
        version = result.stdout.strip().split("\n")[0]
        return True, version
    except Exception:
        return True, "installed (version unknown)"


async def _check_ollama_models() -> list[str]:
    """Get list of locally pulled Ollama models."""
    try:
        import httpx
        ollama_url = os.getenv("OLLAMA_URL", "http://localhost:11434")
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.get(f"{ollama_url}/api/tags")
            if r.status_code == 200:
                models = r.json().get("models", [])
                return [m["name"].split(":")[0] + ":" + m["name"].split(":")[-1]
                        for m in models]
    except Exception:
        pass
    return []


async def _check_ollama_running() -> bool:
    """Check if Ollama API is responding."""
    try:
        import httpx
        ollama_url = os.getenv("OLLAMA_URL", "http://localhost:11434")
        async with httpx.AsyncClient(timeout=3.0) as client:
            r = await client.get(f"{ollama_url}/api/version")
            return r.status_code == 200
    except Exception:
        return False


async def run_doctor():
    """Run full system health check."""
    console.print(Panel(
        "[bold cyan]CYPHEX System Check[/bold cyan]\n"
        "[dim]Verifying dependencies, hardware, and AI models...[/dim]",
        border_style="cyan"
    ))
    console.print()

    # ── System Info ──
    gpu_info = get_gpu_info()
    mode = detect_mode(gpu_info["vram_gb"])

    table = Table(title="System Information", show_header=False, border_style="dim")
    table.add_column("Key", style="bold")
    table.add_column("Value")
    table.add_row("Python", f"{sys.version.split()[0]}")
    table.add_row("Platform", f"{sys.platform} ({platform.machine()})")
    table.add_row("GPU", gpu_info["gpu_name"])
    table.add_row("VRAM", f"{gpu_info['vram_gb']} GB" if gpu_info["vram_gb"] > 0 else "None detected")
    table.add_row("Mode", f"[bold]{mode.upper()}[/bold] — {MODE_DESCRIPTIONS[mode]}")
    console.print(table)
    console.print()

    # ── Dependencies ──
    deps_table = Table(title="Dependencies", border_style="dim")
    deps_table.add_column("Tool", style="bold")
    deps_table.add_column("Status")
    deps_table.add_column("Action", style="dim")

    checks = {
        "git": ("https://git-scm.com", True),
        "node": ("https://nodejs.org", False),
        "npm": ("comes with Node.js", False),
        "docker": ("https://docker.com (optional, for sandbox)", False),
        "ollama": ("https://ollama.ai", mode != "cloud"),
        "semgrep": ("pip install semgrep (optional, 5000+ SAST rules)", False),
        "nuclei": ("https://github.com/projectdiscovery/nuclei (optional, DAST)", False),
    }

    all_ok = True
    for tool, (install_hint, required) in checks.items():
        found, version = _check_binary(tool)
        if found:
            deps_table.add_row(tool, f"[green]✓[/green] {version}", "")
        elif required:
            deps_table.add_row(tool, "[red]✗ missing[/red]", f"Install: {install_hint}")
            all_ok = False
        else:
            deps_table.add_row(tool, "[yellow]○ optional[/yellow]", f"Install: {install_hint}")

    console.print(deps_table)
    console.print()

    # ── Ollama Models ──
    ollama_running = await _check_ollama_running()
    if ollama_running:
        pulled_models = await _check_ollama_models()
        required_models = MODE_MODELS[mode]

        model_table = Table(title=f"AI Models ({mode.upper()} mode)", border_style="dim")
        model_table.add_column("Model", style="bold")
        model_table.add_column("Status")
        model_table.add_column("Action", style="dim")

        for model in required_models:
            # Check if model name matches (handle tag variations)
            model_base = model.split(":")[0]
            found = any(model_base in m for m in pulled_models)
            if found:
                model_table.add_row(model, "[green]✓ pulled[/green]", "")
            else:
                model_table.add_row(
                    model, "[red]✗ not pulled[/red]",
                    f"Run: ollama pull {model}"
                )
                all_ok = False

        console.print(model_table)
    elif mode != "cloud":
        console.print("[red]✗ Ollama is not running[/red]")
        console.print("  → Start with: [bold]ollama serve[/bold]")
        console.print(f"  → Then pull models: [bold]ollama pull {MODE_MODELS[mode][0]}[/bold]")
        all_ok = False
    else:
        # Cloud mode — check for API keys
        groq_key = os.getenv("GROQ_API_KEY", "")
        openai_key = os.getenv("OPENAI_API_KEY", "")
        if groq_key or openai_key:
            console.print("[green]✓[/green] Cloud API key configured")
        else:
            console.print("[red]✗[/red] No cloud API key found")
            console.print("  → Set GROQ_API_KEY or OPENAI_API_KEY in .env")
            all_ok = False

    console.print()

    # ── Verdict ──
    if all_ok:
        console.print(Panel(
            "[bold green]✓ READY[/bold green] — All checks passed. Run [bold]cyphex scan --path ./your-app[/bold] to start.",
            border_style="green"
        ))
    else:
        console.print(Panel(
            "[bold yellow]⚠ PARTIAL[/bold yellow] — Some dependencies missing. Fix the items above, then re-run [bold]cyphex doctor[/bold].",
            border_style="yellow"
        ))

    return all_ok
