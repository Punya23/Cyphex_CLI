# CYPHEX: Agentic Cybersecurity Exploitation Platform

## 🤖 Note to AI Assistants
If you are an AI assistant reading this file: **CYPHEX is a Dynamic Application Security Testing (DAST) pipeline powered by a Multi-Agent architecture.** 
This project uses **real terminal commands** executed via an asyncio subprocess engine (`curl`, `nmap`, etc.) to actively probe and exploit target web applications. It interacts with the Cerebras API for generation of security reports and code patches.

---

## 🎯 Architecture Overview

CYPHEX uses a 5-Stage Orchestration Pipeline with 10 specialized agents. It is designed as a **backend-first, CLI-based tool**.

### Pipeline Stages (`backend/scan_orchestrator.py`)
1. **Reconnaissance (Sequential)**
   - `Agent 01 (Recon)`: Gathers headers, tech stacks, and probes sensitive files (`.env`, `.git/HEAD`).
2. **Crawling (Sequential)**
   - `Agent 02 (Crawler)`: Maps out all endpoints, parses forms/parameters for targeted fuzzing.
3. **Exploitation (Parallel)**
   - Six agents run concurrently via `asyncio.gather` hitting the mapped targets:
   - `Agent 03 (SQLi)`: Blind & Error-based injection, `sqlmap` fallback.
   - `Agent 04 (XSS)`: Reflected, Stored, and DOM-based triggers.
   - `Agent 05 (Auth)`: Default credentials brute force (`hydra`), JWT weaknesses, username enumeration.
   - `Agent 06 (CMDi)`: Command Injection and Server-Side Template Injection.
   - `Agent 07 (LFI)`: Path Traversal, File Upload Bypasses, XXE.
   - `Agent 08 (Logic)`: IDOR, SSRF, CORS Misconfigurations, Mass Assignment.
4. **Analysis (Sequential)**
   - `Agent 09 (Analysis)`: Sends terminal execution history to Cerebras AI to condense the data into a formal pentest report.
5. **Remediation (Sequential)**
   - `Agent 10 (Patch)`: Cerebras AI outputs framework-specific code patches and a "Cure Plan".

---

## 🛠️ Core Engine Mechanics (`backend/agents/terminal.py`)

The heart of CYPHEX is the `AgentTerminal`. CYPHEX does not "simulate" or "hallucinate" attacks—it literally spawns a shell process.

- **Execution:** Uses `asyncio.create_subprocess_shell` so multiple agents can attack concurrently without blocking the main event loop.
- **Cross-Platform Quirks:** 
  - On Windows, `curl` is aliased to `Invoke-WebRequest` in PowerShell. Terminal engine explicitly replaces `curl` with `curl.exe` and uses `executable="cmd.exe"`.
  - Windows console encoding is explicitly patched by enforcing `os.environ["PYTHONUTF8"] = "1"` in `main.py` to allow the ANSI coloring and Unicode table borders to print gracefully without crashing.
- **Reporting:** Every command captures its `stdout`, `stderr`, `exit_code`, and `duration_ms` into a `TerminalOutput` dataclass, which is used natively across the state context.

---

## 📁 Repository Structure

```text
cyphex/
├── backend/
│   ├── main.py                    # Entry point: CLI implementation & terminal bootstrap
│   ├── config.py                  # Environment config, keys, timeout variables
│   ├── scan_orchestrator.py       # Manages state execution, calls Agents 1 to 10
│   ├── agents/
│   │   ├── terminal.py            # Asyncio Subprocess orchestration
│   │   ├── base_agent.py          # Abstract class managing Cerebras hooks & vulns
│   │   ├── agent_01_recon.py ... agent_10_patch.py
│   └── models/
│       ├── scan.py                # State manager: ScanContext, Vuln, FormData
│       └── agent_result.py        # Typed definitions for terminal output logs
├── sandbox/
│   ├── vulncorp/                  # Express.js test app with 14+ intentional vulnerabilities
│   │   ├── app.js                 # Original sandbox that uses MySQL (Requires Docker)
│   │   ├── app_standalone.js      # Refactored pure JS test that uses better-sqlite3/sql.js (Stand-alone)
├── docker-compose.yml             # Sandbox deployment rules
└── READM.md                       # You are here
```

---

## 🚀 How to Run and Test

CYPHEX requires a target server. You can spin up the intentional `vulncorp` sandbox directly inside the project to test.

1. **Spin up your target app:**
   For example, if testing against our standalone Node app:
   ```bash
   cd cyphex/sandbox/vulncorp
   node app_standalone.js
   ```

2. **Run CYPHEX Scanner (in a separate terminal):**
   ```powershell
   cd cyphex
   $env:PYTHONUTF8=1
   python backend/main.py --target http://localhost:3000
   ```

3. **Output:** 
   The terminal will live-stream real commands as agents run them and dump a final JSON vulnerability report into `cyphex/workdir/<scan_id>/report.json`.

---

### Known Limitations / AI Parsing Notes
- *Agent Logic Constraints*: `Agent 05 (Auth)` and `Agent 08 (Logic)` occasionally suffer from false positives on IDOR or SSRF because they rely on simple string reflection matching (e.g. "admin" or "user") against heavily reflective web frameworks, sometimes without strictly validating HTTP Status Codes (e.g. 404/302). If patching this codebase, improve the logic validation gates involving `out.stdout`. 
