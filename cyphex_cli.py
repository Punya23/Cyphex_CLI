"""
CYPHEX CLI — One-command security scanner
Usage:
  python cyphex_cli.py scan --repo https://github.com/user/app
  python cyphex_cli.py scan --path ./my-app
  python cyphex_cli.py scan --path ./backend/target2z/target2
"""
import argparse
import asyncio
import os
import sys
import shutil
import subprocess
import time
import uuid
import json
import glob
import re

os.environ["PYTHONUTF8"] = "1"
os.environ["PYTHONIOENCODING"] = "utf-8"
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "backend", "backend"))

class C:
    R="\033[91m"; G="\033[92m"; Y="\033[93m"; B="\033[94m"
    M="\033[95m"; CY="\033[96m"; W="\033[97m"; BOLD="\033[1m"
    DIM="\033[2m"; RST="\033[0m"

BANNER = f"""
{C.CY}
   _____ __     __ _____   _    _  ______ __   __
  / ____|\\ \\   / /|  __ \\ | |  | ||  ____|\\ \\ / /
 | |      \\ \\_/ / | |__) || |__| || |__    \\ V / 
 | |       \\   /  |  ___/ |  __  ||  __|    > <  
 | |____    | |   | |     | |  | || |____  / . \\ 
  \\_____|   |_|   |_|     |_|  |_||______|/_/ \\_\\
{C.RST}
  {C.BOLD}Autonomous Cyber Defence | v4.3 | OFFLINE-FIRST{C.RST}
  {C.DIM}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{C.RST}
"""

def _load_engine():
    """
    Import the engine lazily so we can show a clean dependency error
    instead of a raw traceback during startup.
    """
    try:
        from cli_engine import CyphexEngine
        return CyphexEngine
    except ModuleNotFoundError as exc:
        missing = getattr(exc, "name", None) or str(exc)
        print(f"{C.R}[ERR]{C.RST} Missing Python dependency: {missing}")
        print("Install required packages and retry:")
        print("  python -m pip install -r backend/backend/requirements.txt numpy scikit-learn joblib")
        raise SystemExit(1)

def main():
    parser = argparse.ArgumentParser(description="CYPHEX CLI")
    sub = parser.add_subparsers(dest="command")

    scan_p = sub.add_parser("scan", help="Scan a codebase")
    scan_p.add_argument("--repo", help="GitHub repo URL to clone and scan")
    scan_p.add_argument("--path", help="Local folder path to scan")
    scan_p.add_argument("--branch", default="main", help="Git branch")
    scan_p.add_argument("--generations", type=int, default=10)
    scan_p.add_argument("--output", help="Save report to file")
    scan_p.add_argument("--no-patch", action="store_true", help="Skip patching")
    scan_p.add_argument(
        "--judge",
        action="store_true",
        help="Deterministic judge mode with machine-readable artifacts",
    )
    scan_p.add_argument(
        "--non-interactive",
        action="store_true",
        help="Do not prompt for patch apply decisions",
    )

    sub.add_parser("doctor", help="Check local runtime/tooling readiness")
    sub.add_parser("council-doctor", help="Check all 4 council models are available in Ollama")

    args = parser.parse_args()
    if not args.command:
        os.system("cls" if os.name == "nt" else "clear")
        print(BANNER)
        parser.print_help()
        return

    if args.command == "doctor":
        os.system("cls" if os.name == "nt" else "clear")
        print(BANNER)
        CyphexEngine = _load_engine()
        engine = CyphexEngine()
        ok = engine.doctor()
        raise SystemExit(0 if ok else 1)

    if args.command == "council-doctor":
        os.system("cls" if os.name == "nt" else "clear")
        print(BANNER)
        import httpx
        from rich.console import Console
        console = Console()

        REQUIRED_MODELS = [
            ("deepseek-coder:1.3b",  "Detector",    "always-on",   1.0),
            ("phi3:mini",             "Validator",   "always-on",   2.2),
            ("llama3.2:3b",           "Narrator",    "phase-swap",  2.0),
            ("cyphex-patch",          "Patch Agent", "patch-only",  4.5),
        ]

        console.print("[bold cyan]CYPHEX Council Model Health Check[/bold cyan]\n")
        all_ok = True
        for tag, role, schedule, vram in REQUIRED_MODELS:
            try:
                r = httpx.post(
                    "http://localhost:11434/api/generate",
                    json={"model": tag, "prompt": "respond with the word ready", "stream": False},
                    timeout=30.0
                )
                response = r.json().get("response", "")
                if "ready" in response.lower():
                    console.print(f"  [green]✓[/green] {role:12} {tag:30} {vram} GB  ({schedule})")
                else:
                    console.print(f"  [yellow]⚠[/yellow] {role:12} {tag:30} {vram} GB  ({schedule}) — unexpected response")
            except Exception:
                console.print(f"  [red]✗[/red] {role:12} {tag:30} NOT FOUND")
                console.print(f"       → Run: [bold]ollama pull {tag}[/bold]")
                all_ok = False

        print()
        if all_ok:
            console.print("[bold green]All council models are ready![/bold green]")
        else:
            console.print("[bold yellow]Some models are missing. Pull them with ollama.[/bold yellow]")
        raise SystemExit(0 if all_ok else 1)

    if args.command == "scan":
        if not args.repo and not args.path:
            print(f"{C.R}Error: Provide --repo or --path{C.RST}")
            return
        os.system("cls" if os.name == "nt" else "clear")
        print(BANNER)
        CyphexEngine = _load_engine()
        engine = CyphexEngine()
        asyncio.run(engine.run(
            repo_url=args.repo,
            local_path=args.path,
            branch=args.branch,
            generations=args.generations,
            output_file=args.output,
            auto_patch=not args.no_patch,
            judge_mode=args.judge,
            non_interactive=args.non_interactive,
        ))

if __name__ == "__main__":
    main()
