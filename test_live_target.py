"""
CYPHEX Immune System — LIVE TEST against NexusBlog (target2z)
=============================================================
Tests the immune system against a REAL vulnerable web application.
Target: http://localhost:3003 (NexusBlog - XSS Showcase)

Phases:
1. Crawl the real target to discover endpoints/forms
2. Build genome from real scan data
3. Generate & test attack payloads against genome
4. Run evolution loop
5. Show what the genome learned
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

TARGET = "http://localhost:3003"

# Colors
class C:
    RED = "\033[91m"; GREEN = "\033[92m"; YELLOW = "\033[93m"
    BLUE = "\033[94m"; CYAN = "\033[96m"; WHITE = "\033[97m"
    BOLD = "\033[1m"; DIM = "\033[2m"; RESET = "\033[0m"


def header(title, emoji=""):
    print(f"\n{C.CYAN}{'='*70}{C.RESET}")
    print(f"  {emoji}  {C.BOLD}{title}{C.RESET}")
    print(f"{C.CYAN}{'='*70}{C.RESET}\n")


async def crawl_target() -> ScanContext:
    """Crawl the real NexusBlog target to discover endpoints and forms."""
    header("PHASE 1: CRAWLING REAL TARGET", "1")
    print(f"  Target: {C.CYAN}{TARGET}{C.RESET}\n")

    context = ScanContext(target_url=TARGET)

    async with httpx.AsyncClient(timeout=10.0) as client:
        # Crawl main pages
        pages = ["/", "/blog", "/search", "/profile", "/feedback", "/admin"]
        discovered_forms = []
        all_endpoints = []

        for page in pages:
            try:
                url = f"{TARGET}{page}"
                resp = await client.get(url)
                status = resp.status_code
                body = resp.text

                print(f"  {C.GREEN}[{status}]{C.RESET} GET {page}")
                all_endpoints.append(url)

                # Extract forms
                form_matches = re.findall(
                    r'<form[^>]*method="(GET|POST)"[^>]*action="([^"]*)"',
                    body, re.IGNORECASE
                )
                for method, action in form_matches:
                    # Extract input names
                    form_section = body[body.find(f'action="{action}"'):]
                    form_section = form_section[:form_section.find('</form>') + 7]
                    inputs = re.findall(r'name="([^"]+)"', form_section)

                    full_action = f"{TARGET}{action}" if action.startswith("/") else action
                    form = FormData(
                        action=full_action,
                        method=method.upper(),
                        inputs=inputs,
                        page=page,
                    )
                    discovered_forms.append(form)
                    print(f"    {C.YELLOW}[FORM]{C.RESET} {method} {action} → inputs: {inputs}")

                # Extract headers
                for key, val in resp.headers.items():
                    context.headers[key] = val

            except Exception as e:
                print(f"  {C.RED}[ERR]{C.RESET} {page}: {e}")

        # Detect framework
        server = context.headers.get("x-powered-by", "")
        if "Express" in server:
            context.framework = "Express.js"
        context.server = context.headers.get("x-powered-by", "Unknown")

        context.all_endpoints = all_endpoints
        context.all_forms = discovered_forms
        context.all_params = [
            ParamData(url=f"{TARGET}/search", name="q", value="test"),
            ParamData(url=f"{TARGET}/admin", name="notice", value="hello"),
        ]

    print(f"\n  {C.BOLD}Results:{C.RESET}")
    print(f"    Endpoints discovered: {len(all_endpoints)}")
    print(f"    Forms discovered: {len(discovered_forms)}")
    print(f"    Framework: {context.framework or 'Unknown'}")
    print(f"    Server: {context.server}")

    return context


async def test_real_payloads(genome: BehavioralGenome):
    """Test actual XSS/SQLi payloads against the LIVE target and genome."""
    header("PHASE 3: TESTING REAL PAYLOADS", "3")

    mutation = MutationEngine()

    # Real attack payloads to test
    attacks = [
        # XSS payloads (the target is vulnerable to these)
        {"payload": "<script>alert(1)</script>", "type": "xss", "target": "/search?q="},
        {"payload": "<img src=x onerror=alert(1)>", "type": "xss", "target": "/search?q="},
        {"payload": "<svg onload=alert(document.cookie)>", "type": "xss", "target": "/search?q="},
        {"payload": "'\"><script>alert('XSS')</script>", "type": "xss", "target": "/search?q="},
        # Obfuscated XSS
        {"payload": "<ScRiPt>alert(1)</sCrIpT>", "type": "xss", "target": "/search?q="},
        {"payload": "%3Cscript%3Ealert(1)%3C/script%3E", "type": "xss", "target": "/search?q="},
        # SQLi attempts (target may not be vuln but genome should still block)
        {"payload": "' OR 1=1--", "type": "sqli", "target": "/search?q="},
        {"payload": "admin'; DROP TABLE users;--", "type": "sqli", "target": "/search?q="},
        # Normal inputs (should NOT be blocked)
        {"payload": "laptop case", "type": "normal", "target": "/search?q="},
        {"payload": "web security", "type": "normal", "target": "/search?q="},
        {"payload": "express js tutorial", "type": "normal", "target": "/search?q="},
    ]

    print(f"  Testing {len(attacks)} payloads against genome...\n")

    correct = 0
    total = len(attacks)
    ep = f"{TARGET}/search"

    async with httpx.AsyncClient(timeout=10.0) as client:
        for atk in attacks:
            payload = atk["payload"]
            is_normal = atk["type"] == "normal"

            # Score with genome
            score = genome.score_request(ep, payload)
            is_blocked = score >= 0.7

            # Also test against real target
            try:
                resp = await client.get(f"{TARGET}{atk['target']}{payload}")
                reflected = payload in resp.text
                real_status = f"reflected={'YES' if reflected else 'no'}"
            except:
                real_status = "err"

            # Check correctness
            if (is_blocked and not is_normal) or (not is_blocked and is_normal):
                correct += 1
                mark = f"{C.GREEN}OK{C.RESET}"
            else:
                mark = f"{C.RED}!!{C.RESET}"

            # Display
            if is_blocked:
                status = f"{C.GREEN}BLOCKED {C.RESET}"
            else:
                status = f"{C.RED}ALLOWED {C.RESET}" if not is_normal else f"{C.DIM}ALLOWED {C.RESET}"

            bar_len = int(score * 20)
            bar = f"{'█' * bar_len}{'░' * (20 - bar_len)}"

            type_label = f"[{atk['type']:>6}]"
            print(f"  {mark} {status} [{bar}] {score:.2f}  {type_label}  {payload[:45]:45}  {C.DIM}{real_status}{C.RESET}")

    print(f"\n  {C.BOLD}Accuracy: {correct}/{total} ({100*correct/total:.0f}%){C.RESET}")
    return correct / total


async def run_live_evolution(context: ScanContext):
    """Run the full evolution loop against the real target data."""
    header("PHASE 4: ADVERSARIAL CO-EVOLUTION (LIVE)", "4")

    print(f"  Running red vs blue evolution with REAL endpoint data from {C.CYAN}{TARGET}{C.RESET}\n")

    controller = EvolutionController()
    results = await controller.run_evolution(
        context,
        generations=10,
        payloads_per_gen=30,
    )

    # Show timeline
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
    print(f"\n  {C.BOLD}Final:{C.RESET}")
    print(f"    Block rate: {summary['initial_block_rate']:.1%} → {C.GREEN}{summary['final_block_rate']:.1%}{C.RESET}")
    print(f"    Total attacks tested: {summary['total_attacks_tested']}")
    print(f"    Endpoints protected: {summary['genome_endpoints']}")

    return controller


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
   {C.BOLD}LIVE TEST — Immune System vs NexusBlog{C.RESET}
   {C.DIM}Target: {TARGET}{C.RESET}
""")

    # Check target is running
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(TARGET)
            print(f"  {C.GREEN}[OK]{C.RESET} Target is running ({resp.status_code})\n")
    except Exception:
        print(f"  {C.RED}[ERR]{C.RESET} Target not running! Start it first:")
        print(f"       cd backend/target2z/target2 && npm start")
        return

    # Phase 1: Crawl
    context = await crawl_target()

    # Phase 2: Build genome
    header("PHASE 2: BUILDING GENOME FROM REAL DATA", "2")
    genome = BehavioralGenome()
    state = genome.build_from_scan(context)
    print(f"  {C.GREEN}[OK]{C.RESET} Genome built with {len(genome.endpoint_profiles)} endpoint profiles")
    print(f"  {C.GREEN}[OK]{C.RESET} Isolation Forest trained for {len(genome.endpoint_models)} endpoints")

    for key, profile in genome.endpoint_profiles.items():
        print(f"    {C.CYAN}{profile.endpoint}{C.RESET} ({profile.method}) → fields: {profile.input_fields}")

    # Phase 3: Test payloads
    accuracy = await test_real_payloads(genome)

    # Phase 4: Evolution
    controller = await run_live_evolution(context)

    # Phase 5: Re-test with hardened genome
    header("PHASE 5: RE-TEST WITH HARDENED GENOME", "5")
    accuracy_after = await test_real_payloads(controller.genome)

    # Final summary
    header("RESULTS", "")
    print(f"  {C.BOLD}Before Evolution:{C.RESET} {accuracy:.0%} accuracy")
    print(f"  {C.BOLD}After Evolution:{C.RESET}  {C.GREEN}{accuracy_after:.0%} accuracy{C.RESET}")
    improvement = accuracy_after - accuracy
    if improvement > 0:
        print(f"  {C.BOLD}Improvement:{C.RESET}      {C.GREEN}+{improvement:.0%}{C.RESET}")
    print(f"\n  {C.GREEN}Immune system tested against REAL vulnerable target.{C.RESET}")
    print(f"  {C.DIM}No LLM was used. All scoring is ML + heuristic.{C.RESET}\n")


if __name__ == "__main__":
    asyncio.run(main())
