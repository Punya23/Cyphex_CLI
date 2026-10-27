import { FootageScene } from "../components/FootageScene";
import { C } from "../theme";

// Scenes built from the real recordings (public/footage/<clip>.mp4, made by scripts/build_footage.py).
// Frame numbers are relative to each scene. The camera stays still: the only move in the whole
// film is the zoom onto the buddy mascot in the intro.
// Every number, model name and command on a card is read off a recording, the README or /help.

export const RealIntro: React.FC = () => (
  <FootageScene
    clip="intro"
    eyebrow="Live run · cx deep"
    headline="One command. Ten phases."
    cards={[
      { at: 14, title: "cx deep ./vibemart", sub: "Static + DAST + 13 DeepAgents swarm" },
      { at: 55, title: "TOOL READINESS 5/5", sub: "Git · Docker · Ollama · Semgrep · Nuclei" },
      { at: 100, title: "LIVE BUDDY", sub: "The mascot mirrors what the agent is doing" },
    ]}
    zoom={[
      { f: 0, cx: 0.5, cy: 0.5, z: 1 },
      { f: 92, cx: 0.5, cy: 0.5, z: 1 },
      { f: 128, cx: 0.14, cy: 0.9, z: 2 },
    ]}
    marks={[{ from: 100, to: 165, x: 0.005, y: 0.87, w: 0.08, h: 0.12 }]}
  />
);

// Webhook setup: paste one link, the terminal confirms, Cyphex Buddy says hello in Google Chat.
// The webhook URL and token the terminal prints are blanked in the clip itself (scripts/build_footage.py),
// and the Chat sidebar (other people's names) is blurred.
export const RealConnect: React.FC = () => (
  <FootageScene
    clip="connect"
    eyebrow="Google Chat · /webhook"
    headline="One link. Connected."
    note="1.3× speed"
    cards={[
      { at: 10, title: "/WEBHOOK <LINK>", sub: "Connect Google Chat or Slack: paste the space's webhook link" },
      { at: 62, title: "CONNECTED", sub: "“Connected to Google Chat”: scan updates and PR approvals go there", color: C.green },
      { at: 135, title: "CYPHEX BUDDY SAYS HELLO", sub: "The first message lands in the Chat space", color: C.green },
      { at: 190, title: "LINK HIDDEN", sub: "The webhook URL and token are redacted in this video", color: C.amber },
    ]}
  />
);

export const RealScan: React.FC = () => (
  <FootageScene
    clip="scan"
    eyebrow="Phases 2–3"
    headline="Find it. Run it. Safely."
    note="0.75× speed"
    cards={[
      { at: 6, title: "SEMGREP · 8 FILES", sub: "SQL injection (CWE-89) · command injection (CWE-78)" },
      { at: 138, title: "DOCKER SANDBOX", sub: "No Dockerfile? One is generated and built" },
      { at: 178, title: "LIVE TARGET", sub: "The app is served on localhost, isolated", color: C.green },
    ]}
  />
);

export const RealSwarm: React.FC = () => (
  <FootageScene
    clip="swarm"
    eyebrow="Phase 4 · DeepAgents"
    headline="13 agents. 4 parallel groups."
    cards={[
      { at: 4, title: "AGENTS LAUNCH", sub: "Path traversal · CMDi · SSRF · IDOR · SSTI · XXE" },
      { at: 55, title: "ORACLE-GUIDED", sub: "Each agent is planned by a local model", chips: ["qwen2.5-coder:7b"] },
      { at: 100, title: "SSTI HIT", sub: "{{7*7}} came back as 49: template injection confirmed", color: C.red },
      { at: 190, title: "13 AGENTS · 4 GROUPS", sub: "Run in parallel groups on local models only" },
    ]}
  />
);

// The flow the viewer should follow: plan → blocked → adapt → adapt → confirmed.
export const RealHypothesis: React.FC = () => (
  <FootageScene
    clip="hyp"
    eyebrow="Reasoning loop"
    headline="Hypothesize. Probe. Adapt."
    note="2× speed"
    cards={[
      { at: 4, title: "1 · ATTACK PLAN", sub: "6 hypotheses for SQL injection, ranked by severity", chips: ["qwen2.5-coder:7b"] },
      { at: 102, title: "2 · BLOCKED", sub: "The app's own guard stopped the XSS probe: 100% confidence", color: C.amber },
      { at: 165, title: "3 · ADAPT · 85%", sub: "Judge says retry: mutate the payload", chips: ["llama3.1:8b"], color: C.amber },
      { at: 300, title: "4 · ADAPT · 78%", sub: "Next evasion variant, next probe", color: C.amber },
      { at: 335, title: "5 · CONFIRMED · 90%", sub: "Payload breached: the response matches the hypothesis", color: C.green },
    ]}
  />
);

export const RealCouncil: React.FC = () => (
  <FootageScene
    clip="council"
    eyebrow="Council"
    headline="Three local models vote."
    note="2× speed"
    cards={[
      {
        at: 8,
        title: "VALIDATORS",
        sub: "Every finding is checked against false positives",
        chips: ["deepseek-coder:6.7b", "llama3.1:8b", "qwen2.5-coder:7b"],
      },
      { at: 60, title: "VRAM-AWARE", sub: "Low RAM? Models load one at a time" },
      { at: 112, title: "RESULT", sub: "1 finding validated · 0 false positives discarded", color: C.green },
    ]}
  />
);

export const RealGenome: React.FC = () => (
  <FootageScene
    clip="genome"
    eyebrow="Phase 5 · immune genome"
    headline="It learns your app's normal."
    note="0.6× speed"
    cards={[
      { at: 10, title: "ENDPOINT MAP", sub: "20 live endpoints profiled" },
      { at: 70, title: "15-D FEATURE VECTOR", sub: "entropy · length · symbols · SQLi score …" },
      { at: 135, title: "GENOME SCORING", sub: "' OR 1=1-- → 1.000 BLOCK · normal search → ALLOW" },
      { at: 190, title: "SAVED · SIGNED .pkl", sub: "HMAC sidecar + portable .cxgenome bundle", color: C.green },
    ]}
  />
);

export const RealArena: React.FC = () => (
  <FootageScene
    clip="arena"
    eyebrow="Phase 6 · attack sim"
    headline="It attacks its own defences."
    cards={[
      { at: 8, title: "BEFORE → AFTER", sub: "Each attack was ALLOWED before hardening, BLOCKED after" },
      { at: 64, title: "DEFENSE RATE 7/8 (88%)", sub: "False positives: 0", color: C.green },
      { at: 112, title: "SECURITY REPORT", sub: "Score 24/100 before patching", color: C.amber },
    ]}
  />
);

export const RealPatch: React.FC = () => (
  <FootageScene
    clip="patch"
    eyebrow="Phases 8–9 · patching"
    headline="Local models write and review the fix."
    note="1.5–2.2× speed"
    cards={[
      { at: 10, title: "RAG CONTEXT", sub: "Knowledge tree + code index. No embeddings, no API" },
      { at: 70, title: "META-REASONING", sub: "9 of 16 strategies · self-consistency vote" },
      { at: 160, title: "PATCHER", sub: "Generating 6 patches", chips: ["qwen2.5-coder:7b"] },
      {
        at: 225,
        title: "REVIEWERS",
        sub: "Both vote True: patch approved",
        chips: ["llama3.1:8b", "deepseek-coder:6.7b"],
        color: C.green,
      },
    ]}
  />
);

// The Google Sheet fills with every endpoint and vulnerability as the scan runs.
export const RealSheet: React.FC = () => (
  <FootageScene
    clip="sheet"
    eyebrow="Google Sheets · /sheet"
    headline="Every finding, live."
    note="2.2× speed"
    cards={[
      { at: 8, title: "/SHEET <WEB-APP URL>", sub: "Link a sheet once; every attack attempt is appended" },
      { at: 48, title: "ENDPOINT · PAYLOAD · CWE", sub: "Agent, severity, outcome and confidence on every row" },
      { at: 100, title: "SCAN START / END", sub: "Banner rows carry the score change and fixes applied", color: C.green },
    ]}
  />
);

// Cyphex Buddy posts each scan step to the Chat space as it happens.
export const RealChat: React.FC = () => (
  <FootageScene
    clip="chat"
    eyebrow="Google Chat · live updates"
    headline="Know what's happening."
    note="1.3× speed"
    cards={[
      { at: 8, title: "STEP-BY-STEP", sub: "Each of the 10 phases posts its own message" },
      { at: 55, title: "PLAIN ENGLISH", sub: "“Reading your code for weak spots, without running it.”" },
      { at: 110, title: "IN THE BACKGROUND", sub: "Findings, reports and PR approvals arrive in the space", color: C.green },
    ]}
  />
);
