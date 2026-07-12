#!/usr/bin/env python3
"""
CYPHEX — Interactive CLI (cx)
Claude/Codex-style REPL with slash commands.

Usage:
    python3 cx.py              → drops into interactive session
    python3 cx.py scan         → quick full scan (prompts for path)
    python3 cx.py <target>     → auto-detect target and scan
"""
import asyncio
import os
import sys
import shutil
import subprocess
import readline
import glob
import time
import textwrap

# ── UTF-8 everywhere ──────────────────────────────────────────────────────────
os.environ["PYTHONUTF8"] = "1"
os.environ["PYTHONIOENCODING"] = "utf-8"
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


# ── Load .env ─────────────────────────────────────────────────────────────────
def _load_env():
    env = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    if os.path.exists(env):
        with open(env) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip("'\""))
_load_env()

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "backend", "backend"))


# ── Colours ───────────────────────────────────────────────────────────────────
class C:
    CYAN   = "\033[96m"
    NEON   = "\033[92m"
    RED    = "\033[91m"
    YEL    = "\033[93m"
    BLUE   = "\033[94m"
    GREY   = "\033[90m"
    BOLD   = "\033[1m"
    DIM    = "\033[2m"
    RST    = "\033[0m"
    ITALIC = "\033[3m"
    UL     = "\033[4m"


# ── Banner ────────────────────────────────────────────────────────────────────
BANNER = f"""
{C.CYAN}{C.BOLD}
 ██████╗██╗   ██╗██████╗ ██╗  ██╗███████╗██╗  ██╗
██╔════╝╚██╗ ██╔╝██╔══██╗██║  ██║██╔════╝╚██╗██╔╝
██║      ╚████╔╝ ██████╔╝███████║█████╗   ╚███╔╝ 
██║       ╚██╔╝  ██╔═══╝ ██╔══██║██╔══╝   ██╔██╗ 
╚██████╗   ██║   ██║     ██║  ██║███████╗██╔╝ ██╗
 ╚═════╝   ╚═╝   ╚═╝     ╚═╝  ╚═╝╚══════╝╚═╝  ╚═╝{C.RST}
{C.GREY}  Autonomous Cyber Defence · AI-Powered · Offline-First{C.RST}
{C.DIM}  Type {C.CYAN}/help{C.DIM} to see all commands · {C.CYAN}Tab{C.DIM} for autocomplete{C.RST}
"""

QUICK_HELP = f"""
{C.CYAN}{C.BOLD}Available Commands{C.RST}
{C.DIM}─────────────────────────────────────────────────────────────{C.RST}

  {C.NEON}/scan{C.RST}              Scan a target (prompts for path/URL)
  {C.NEON}/scan <path>{C.RST}       Scan a local directory
  {C.NEON}/scan <github-url>{C.RST} Clone and scan a GitHub repo
  {C.NEON}/deep{C.RST}              Full DeepAgents + network scan (recommended)
  {C.NEON}/deep <path>{C.RST}       Full DeepAgents scan on a local path
  {C.NEON}/net{C.RST}               Network discovery & vulnerability map
  {C.NEON}/net <host>{C.RST}        Audit a specific host or CIDR range
  {C.NEON}/watch{C.RST}             Start RASP auto-healing daemon
  {C.NEON}/doctor{C.RST}            Check all models, tools, and dependencies
  {C.NEON}/models{C.RST}            List available local Ollama models
  {C.NEON}/history{C.RST}           Show recent scans
  {C.NEON}/clear{C.RST}             Clear the screen
  {C.NEON}/exit{C.RST}  {C.NEON}/quit{C.RST}      Exit CYPHEX

{C.DIM}─────────────────────────────────────────────────────────────
  Tip: just type a path or URL and press Enter to scan it{C.RST}
"""


# ── Readline autocomplete ──────────────────────────────────────────────────────
COMMANDS = [
    "/scan", "/deep", "/net", "/netmap", "/netwatch", "/netaudit",
    "/watch", "/doctor", "/models", "/history", "/clear", "/exit", "/quit", "/help",
]

def _completer(text, state):
    options = [c for c in COMMANDS if c.startswith(text)]
    # Also complete file paths
    if text.startswith("/") and not any(text.startswith(c) for c in COMMANDS):
        options = glob.glob(text + "*")
    elif not text.startswith("/"):
        options += glob.glob(text + "*")
    if state < len(options):
        return options[state]
    return None

readline.set_completer(_completer)
readline.parse_and_bind("tab: complete")
readline.set_completer_delims(" \t\n")


# ── Session state ─────────────────────────────────────────────────────────────
_session = {
    "last_path": None,
    "last_target": None,
    "history": [],
}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _clear():
    os.system("cls" if os.name == "nt" else "clear")

def _spinner(msg: str):
    """Print a status line."""
    print(f"\n  {C.CYAN}◆{C.RST} {msg}")

def _ok(msg: str):
    print(f"  {C.NEON}✓{C.RST} {msg}")

def _warn(msg: str):
    print(f"  {C.YEL}⚠{C.RST} {msg}")

def _err(msg: str):
    print(f"  {C.RED}✗{C.RST} {msg}")

def _dim(msg: str):
    print(f"  {C.GREY}{msg}{C.RST}")

def _prompt_path(prompt_text: str = "Target path or URL") -> str:
    """Prompt the user for a path with tab completion."""
    try:
        val = input(f"  {C.CYAN}❯{C.RST} {C.BOLD}{prompt_text}:{C.RST} ").strip()
    except (KeyboardInterrupt, EOFError):
        print()
        return ""
    return val

def _run_cyphex(args: list[str]):
    """Delegate to the existing cyphex_cli.py with the given args."""
    script = os.path.join(os.path.dirname(__file__), "cyphex_cli.py")
    cmd = [sys.executable, script] + args
    try:
        subprocess.run(cmd)
    except KeyboardInterrupt:
        print(f"\n  {C.YEL}[Scan interrupted]{C.RST}")

def _record_history(cmd: str, target: str):
    _session["history"].append({
        "time": time.strftime("%H:%M"),
        "cmd": cmd,
        "target": target,
    })


# ── Command handlers ───────────────────────────────────────────────────────────

def _cmd_scan(arg: str, deep: bool = False, network: bool = False):
    """Run a scan — optionally full DeepAgents + network."""
    target = arg.strip() if arg else ""

    if not target:
        # Was anything scanned before? Offer it as default.
        default = _session.get("last_path") or _session.get("last_target")
        hint = f" [{C.GREY}{default}{C.RST}]" if default else ""
        target = _prompt_path(f"Path or GitHub URL{hint}")
        if not target:
            if default:
                target = default
            else:
                _err("No target specified.")
                return

    target = target.strip()

    # Build args
    scan_args = ["scan"]
    if target.startswith("http") and "github.com" in target:
        scan_args += ["--repo", target]
        _spinner(f"Cloning and scanning {C.CYAN}{target}{C.RST}")
    else:
        # Expand path
        expanded = os.path.expanduser(target)
        if not os.path.exists(expanded):
            _err(f"Path not found: {expanded}")
            return
        scan_args += ["--path", expanded]
        _spinner(f"Scanning {C.CYAN}{expanded}{C.RST}")

    if deep or network:
        scan_args += ["--network"]
    if deep:
        scan_args += ["--use-deepagents"]

    scan_args += ["--non-interactive"]

    mode = "DeepAgents + Network" if deep else ("Network" if network else "Static + DAST")
    _dim(f"Mode: {mode}")
    print()

    _session["last_path"] = target
    _record_history("/deep" if deep else "/scan", target)
    _run_cyphex(scan_args)


def _cmd_net(arg: str):
    """Run a network scan / audit."""
    if arg:
        # Specific host — run netaudit
        _spinner(f"Running network audit on {C.CYAN}{arg}{C.RST}")
        _run_cyphex(["netaudit", "--host", arg, "--oracle"])
        _record_history("/net", arg)
    else:
        # Auto-detect subnet
        _spinner("Running network discovery on local subnet...")
        _run_cyphex(["netmap"])
        _record_history("/net", "local subnet")


def _cmd_doctor():
    _spinner("Running system health check...")
    _run_cyphex(["doctor"])


def _cmd_watch():
    _spinner("Starting RASP auto-healing daemon (Ctrl+C to stop)...")
    _run_cyphex(["watch"])


def _cmd_models():
    """List available Ollama models."""
    print()
    try:
        import httpx
        r = httpx.get("http://localhost:11434/api/tags", timeout=5)
        models = r.json().get("models", [])
        if not models:
            _warn("No models found. Run: ollama pull llama3.1:8b")
            return
        print(f"  {C.CYAN}{C.BOLD}Available local models:{C.RST}")
        print(f"  {C.GREY}{'─' * 50}{C.RST}")
        for m in models:
            name  = m.get("name", "?")
            size  = m.get("size", 0)
            size_gb = f"{size / 1e9:.1f} GB" if size else ""
            print(f"  {C.NEON}●{C.RST} {C.BOLD}{name:<30}{C.RST}  {C.GREY}{size_gb}{C.RST}")
    except Exception as e:
        _err(f"Cannot reach Ollama: {e}")
        _dim("Start Ollama with: ollama serve")


def _cmd_history():
    if not _session["history"]:
        _dim("No scans in this session yet.")
        return
    print(f"\n  {C.CYAN}{C.BOLD}Scan history this session:{C.RST}")
    print(f"  {C.GREY}{'─' * 50}{C.RST}")
    for item in _session["history"][-10:]:
        print(f"  {C.GREY}{item['time']}{C.RST}  {C.NEON}{item['cmd']:<8}{C.RST}  {item['target']}")


def _auto_scan(raw: str):
    """
    User typed something that isn't a slash command.
    If it looks like a path or URL, scan it.
    """
    raw = raw.strip()
    if not raw:
        return
    is_url  = raw.startswith("http")
    is_path = os.path.exists(os.path.expanduser(raw)) or raw.startswith("./") or raw.startswith("~/")
    if is_url or is_path:
        _cmd_scan(raw)
    else:
        _err(f"Unknown command or path not found: {C.BOLD}{raw}{C.RST}")
        _dim("Type /help to see available commands.")


# ── Main REPL ─────────────────────────────────────────────────────────────────

def _handle(line: str):
    """Parse and dispatch one input line."""
    line = line.strip()
    if not line:
        return

    parts = line.split(None, 1)
    cmd   = parts[0].lower()
    arg   = parts[1] if len(parts) > 1 else ""

    match cmd:
        case "/help" | "help":
            print(QUICK_HELP)

        case "/scan":
            _cmd_scan(arg)

        case "/deep":
            _cmd_scan(arg, deep=True)

        case "/net" | "/netmap":
            _cmd_net(arg)

        case "/netwatch":
            _spinner("Starting network anomaly monitor (Ctrl+C to stop)...")
            _run_cyphex(["netwatch"])

        case "/netaudit":
            host = arg or _prompt_path("Host IP to audit")
            if host:
                _run_cyphex(["netaudit", "--host", host, "--oracle"])

        case "/watch":
            _cmd_watch()

        case "/doctor":
            _cmd_doctor()

        case "/models":
            _cmd_models()

        case "/history":
            _cmd_history()

        case "/clear" | "clear":
            _clear()
            print(BANNER)

        case "/exit" | "/quit" | "exit" | "quit":
            print(f"\n  {C.CYAN}Goodbye.{C.RST}\n")
            sys.exit(0)

        case _:
            _auto_scan(line)


def _repl():
    """Drop into the interactive REPL."""
    _clear()
    print(BANNER)

    prompt = f"{C.CYAN}cx{C.RST}{C.GREY}>{C.RST} "

    while True:
        try:
            line = input(prompt).strip()
        except KeyboardInterrupt:
            # Ctrl+C → new line, don't quit
            print()
            continue
        except EOFError:
            # Ctrl+D → quit
            print(f"\n  {C.CYAN}Goodbye.{C.RST}\n")
            break

        _handle(line)


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    # If called with args, handle them directly then drop into REPL or exit
    if len(sys.argv) > 1:
        raw_arg = " ".join(sys.argv[1:])
        first   = sys.argv[1].lower()

        # cx scan [path]        → /scan
        if first in ("scan", "/scan"):
            _clear()
            print(BANNER)
            remainder = " ".join(sys.argv[2:])
            _cmd_scan(remainder)
            return

        # cx deep [path]        → /deep
        if first in ("deep", "/deep"):
            _clear()
            print(BANNER)
            remainder = " ".join(sys.argv[2:])
            _cmd_scan(remainder, deep=True)
            return

        # cx net [host]
        if first in ("net", "/net", "netmap", "/netmap"):
            _clear()
            print(BANNER)
            _cmd_net(" ".join(sys.argv[2:]))
            return

        # cx doctor
        if first in ("doctor", "/doctor"):
            _clear()
            print(BANNER)
            _cmd_doctor()
            return

        # cx models
        if first in ("models", "/models"):
            _clear()
            print(BANNER)
            _cmd_models()
            return

        # cx <path/url> → auto-scan
        _clear()
        print(BANNER)
        _cmd_scan(raw_arg)
        return

    # No args → interactive REPL
    _repl()


if __name__ == "__main__":
    main()
