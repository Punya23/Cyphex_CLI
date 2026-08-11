<p align="center">
  <img src="https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white" />
  <img src="https://img.shields.io/badge/Ollama-Local_AI-000000?style=for-the-badge&logo=ollama&logoColor=white" />
  <img src="https://img.shields.io/badge/Docker-Sandbox-2496ED?style=for-the-badge&logo=docker&logoColor=white" />
  <img src="https://img.shields.io/badge/Semgrep-SAST-4B275F?style=for-the-badge" />
  <img src="https://img.shields.io/badge/Nuclei-DAST-FF6C37?style=for-the-badge" />
  <img src="https://img.shields.io/badge/100%25-Offline-2ea44f?style=for-the-badge" />
  <img src="https://img.shields.io/badge/License-MIT-green?style=for-the-badge" />
</p>

<h1 align="center">🛡️ CYPHEX</h1>
<p align="center"><sub><b>Autonomous AI Cyber-Defence Engine — scans, attacks, debates, evolves, and patches your code. 100% offline. Zero API keys.</b></sub></p>

<p align="center">
  Point it at a folder or a GitHub repo. It deploys your app in a sandbox, unleashes a swarm of
  <b>Oracle-guided AI attack agents</b>, validates every finding through a <b>multi-model council</b>,
  evolves a self-taught <b>behavioural immune system</b>, and <b>auto-patches your source code</b> —
  then proves the fix with a re-scan. Your code never leaves your machine.
</p>

<p align="center">
  <a href="#-quick-start">Quick Start</a> · <a href="#-what-makes-cyphex-different">Highlights</a> ·
  <a href="#-how-it-works">Pipeline</a> · <a href="#-usage">Usage</a> ·
  <a href="CYPHEX_PRD.md">Full Docs (PRD)</a>
</p>

---

## 🎯 The Problem

> **Vibe-coded apps ship fast — and ship with vulnerabilities no one checks.**

- **SAST** finds code patterns but can't see runtime behaviour.
- **DAST** attacks the running app but doesn't understand the source — it gives you a URL, not a fix.
- **Neither fixes anything.** You're left with noisy reports and zero patches.
- **Cloud tools need API keys** and upload your proprietary code to third-party servers.

CYPHEX closes the loop: **find → attack → verify → fix → harden**, in one command, fully local.

---

## ⭐ What Makes CYPHEX Different

### 🕵️ 1. DeepAgents — an Oracle-guided attack swarm

**10 specialized AI attack agents**, one per vulnerability class, that don't run a fixed script — they *adapt*. Each runs an **Observe → Think → Act** loop: probe the live app, let the Oracle judge the response, mutate the payload, and try again.

| Agent | Targets | Agent | Targets |
|---|---|---|---|
| `DeepSQLiAgent` | SQL Injection | `DeepSSRFAgent` | Server-Side Request Forgery |
| `DeepXSSAgent` | Cross-Site Scripting | `DeepSSTIAgent` | Template Injection |
| `DeepCMDiAgent` | Command Injection | `DeepPathTraversalAgent` | Path Traversal / LFI |
| `DeepAuthAgent` | Auth Bypass / Priv-Esc | `DeepXXEAgent` | XML External Entity |
| `DeepIDORAgent` | Insecure Direct Object Ref | `DeepBusinessLogicAgent` | Business-Logic Flaws |

*Plus crawler, API-discovery, and network reconnaissance agents. A **dead-route guard** means agents never waste time attacking endpoints that don't exist — and confirmed exploits are chained into **multi-step attack paths** (e.g. unauth data leak → admin takeover).*

### 🧠 2. Oracle Deep Thinking — making small local models think like a pentester

The **Oracle** is the local-LLM brain behind every DeepAgent. It turns a 7B model into a reasoning attacker:

- **`plan()`** — reads the attack surface and generates 5–8 prioritized attack **hypotheses** (highest-impact / cheapest-to-test first).
- **`decide()`** — judges each probe's response (status, size, **timing vs. baseline**, body) and returns *confirmed / adapt / abandoned* with a confidence score and structured evidence.
- **`mutate()`** — evolves a failing payload into new evasion variants.

Layered on top: a **meta-reasoning router** that assigns each vulnerability a strategy by difficulty (Critical/hard-CWE → **Self-Consistency** K-vote, High → **Chain-of-Thought**), **grounded reflexion** (retry a rejected fix with the critique injected), and **per-patch reasoning trees** for full auditability. *No cloud. No API cost. Just local compute spent where it pays off.*

### 📚 3. Vectorless RAG — full code context, zero embeddings

Small models write good patches only with good context. CYPHEX gives them precise context **without any embeddings or vector database**: a keyword/regex **code tree index** that, per vulnerability, extracts the **whole brace-balanced enclosing function**, the file's imports, a **CWE fix recipe** from a security knowledge base, and an **in-repo secure example** to copy the codebase's own style.

> No VRAM for embeddings. No vector store to spin up. No data leaving the machine. Just high-signal context assembled in milliseconds.

### ☁️ 4. Cloud & AWS Attack Coverage — stops credential theft from the metadata service

CYPHEX specifically hunts the **#1 cloud-credential-theft vector**: **SSRF to the AWS EC2 metadata endpoint** `http://169.254.169.254/latest/meta-data/`. The `DeepSSRFAgent` probes it, the **behavioural genome** and **RASP shield** block it, and the attack-simulation arena demonstrates the before/after.

You can also **validate the immune system against real cyber-attack datasets** — point the benchmark at an external labelled corpus (e.g. **CSE-CIC-IDS2018** web-attack payloads) with `cyphex benchmark --data <file>` to score detection on research-grade data, not just synthetic samples.

---

## 🧬 The Behavioural Immune System

Instead of matching a database of known signatures, CYPHEX **learns what *normal* looks like for *your* app** and blocks anomalies.

- **Behavioural Genome** — a per-endpoint **Isolation Forest** trained on a **15-dimension feature vector** (entropy, special-char ratio, SQLi/CMDi patterns, traversal depth, bracket imbalance…). Scores every payload 0.0 (normal) → 1.0 (anomalous); **BLOCK ≥ 0.7**.
- **Adversarial Co-Evolution** — an AI **red team** mutates attacks while a **blue team** retrains the genome, generation after generation, until the block-rate converges (e.g. **63% → 100%**). The genome hardens against attacks it discovered *itself*, fully offline.
- **Measured quality (`cyphex benchmark`):** **91.3% recall · 97.7% precision · 94.4% F1 · 3.3% false-positive rate · ~0.04 ms/sample.** Exits non-zero if recall < 80% or FPR > 10% — a ready-made **CI gate**.

## 🛡️ RASP + Auto-Heal Daemon

A **zero-dependency drop-in shield** (`cyphex-rasp.js`, one line in your Express app) inspects every live request, blocks attacks with a **403**, and — using a **stack-trace capture** — pinpoints the *exact vulnerable `file:line`* (solving the "DAST disconnect"). It ships that to the **`cyphex watch` daemon**, which has the AI council **auto-patch the source code in place**. Detected in production → blocked → healed.

---

## 🔬 How It Works — the 9-Step Pipeline

| # | Waypoint | What happens |
|---|---|---|
| 1 | **Get Source** | Copy/clone target into a sandbox working copy; detect framework. |
| 2 | **Static Analysis** | Semgrep **+** built-in 20-language scanner, **merged**. |
| 3 | **Deploy Sandbox** | Real Docker container (**auto-generated Dockerfile** if none) or native fallback, with logs. |
| 3b | **Network Scan** *(opt)* | Host/port sweep + per-device network genome (25-D). |
| 4 | **Dynamic Scan** | Crawler + API discovery + Nuclei + **10 Oracle-guided DeepAgents**. |
| 5 | **Build Genome** | Learn "normal"; run adversarial co-evolution to convergence. |
| 6 | **Attack Arena** | BEFORE/AFTER genome-defense demo (defense rate + false positives). |
| 7 | **Security Report** | AI council writes it; a **second model fact-checks** for invented findings. |
| 8 | **Patch + Verify** | Per vuln: Template → **Vectorless RAG** → LLM → Council → **Verify Gate**. |
| 9 | **Final Score** | Before/after Security Posture Score from **only verified fixes**. |

**The Verify Gate** is CYPHEX's honesty guarantee — a patch counts as *fixed* only if a re-scan confirms the finding is gone, syntax is valid (`node --check` / `py_compile`), no suppression comments were added, and the diff stays within a severity-scaled blast radius. Anything else is **rolled back**.

---

## 🚀 Quick Start

```bash
# 1. Clone
git clone -b updates_p1 https://github.com/Punya23/Cyphex_CLI.git
cd Cyphex_CLI

# 2. Install
pip install -e .

# 3. Pull at least one local model
ollama pull qwen2.5-coder:7b     # patcher / oracle
ollama pull llama3.1:8b          # reviewer / analyst

# 4. Scan (and auto-patch) the bundled vulnerable app
cyphex scan --path ./vibemart
```

### Prerequisites

| Tool | Required | Why |
|---|---|---|
| **Python 3.11+** | ✅ | Runtime |
| **Ollama** | ✅ | Local AI models (no API keys) |
| **Docker** | ⚡ Recommended | Real sandbox isolation + logs |
| **Node.js 18+** | ⚡ Recommended | Scanning & syntax-checking JS/TS |
| **Semgrep / Nuclei** | 🔧 Optional | Extra SAST rules / DAST templates (`cyphex setup` installs them) |

```bash
cyphex doctor    # verify models, tools, and dependencies
```

---

## 💻 Usage

```bash
/scan <target> [--network] [--deepagents] [--full] [--no-patch]
/deep <target>          # + Oracle-guided DeepAgents swarm
/full <target>          # DeepAgents + network sweep (everything)
/net [host]             # network discovery / audit
/netwatch               # live network anomaly monitor
/watch                  # RASP auto-heal daemon
/benchmark [corpus]     # score the immune system (precision/recall/F1)
/setup  /doctor  /models  /help
```

```bash
# Or non-interactively (CI-friendly):
cyphex scan --repo https://github.com/user/app.git --use-deepagents --network
cyphex benchmark --data cic-ids2018.csv   # validate on external cyber data
```

---

## 🛠️ Tech Stack

| Layer | Tech |
|---|---|
| **Local AI** | Ollama — `qwen2.5-coder:7b` (patcher/oracle), `llama3.1:8b` (analyst/reviewer), `deepseek-coder:6.7b` (reviewer), `nomic-embed-text` (memory) |
| **SAST** | Semgrep + built-in 20-language regex scanner |
| **DAST** | Nuclei, OWASP ZAP, + 10 DeepAgents |
| **Sandbox** | Docker (auto-Dockerfile) / native subprocess |
| **Immune System** | scikit-learn Isolation Forest (CPU-only, offline) |
| **Memory** | per-project patch cache · cognee cross-project knowledge graph · cross-scan session memory |
| **Core** | Python 3.11+ · httpx · rich · numpy |

---

## 🔐 Security & Ethics

- **100% offline.** No cloud APIs, no keys, no billing. Source code, reports, and patches never leave your machine.
- **Sandbox-only offense.** All attacks run against *your own* app inside an isolated sandbox — never against live external systems.
- **Fail-closed safety.** Path-containment + symlink rejection on every write, atomic write + auto-rollback, and **HMAC-signed** model caches (poisoned pickles refused).
- **Graceful degradation.** Missing Docker / scikit-learn / Semgrep / Nuclei → CYPHEX degrades, never crashes. Runs down to a Raspberry Pi 5.

---

## 📚 Full Documentation

The complete concept reference — every subsystem explained as *What / How / Why / Where*, plus requirements, metrics, and roadmap — lives in **[CYPHEX_PRD.md](CYPHEX_PRD.md)**.

---

## 📄 License

MIT — see [LICENSE](LICENSE).

<p align="center"><br><b>CYPHEX</b> — because your code deserves an immune system.<br>
<i>Autonomous scanning · Oracle-guided attacks · AI council debate · Adversarial evolution · Verified auto-patching.</i><br>
<b>One command. Zero APIs. 100% local.</b></p>
