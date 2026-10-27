import { AbsoluteFill, Easing, interpolate, useCurrentFrame } from "remotion";
import { FlowWire } from "../components/FlowWire";
import { Appear, Eyebrow, Headline } from "../components/kit";
import { C, CLAMP, FONT_MONO } from "../theme";

const EASE_OUT = Easing.bezier(0.215, 0.61, 0.355, 1); // power3.out

// The real DeepAgents loop (README §1): one shared Oracle, three local models.
const NODES = [
  { name: "PLAN", model: "qwen2.5-coder:7b", role: "ranked hypotheses" },
  { name: "PROBE", model: "HTTP request", role: "send the payload" },
  { name: "DECIDE", model: "llama3.1:8b", role: "confirm / adapt / drop" },
  { name: "MUTATE", model: "deepseek-coder:6.7b", role: "evasion variant" },
];
const NODE_W = 320;
const NODE_X = [150, 570, 990, 1410];
const NODE_Y = 345; // top edge
const NODE_H = 160;
const MID_Y = NODE_Y + NODE_H / 2;

// Walk through the loop: plan once, then probe → decide → mutate until confirmed.
const SEQ = [0, 1, 2, 3, 1, 2, 3, 1, 2];
const FIRST = 28;
const STEP = 22;

// Illustrative trace (a real agent's payloads vary); revealed at each DECIDE step.
const TRACE = [
  { payload: "' OR 1=1--", verdict: "adapt · filtered", step: 2, color: C.amber },
  { payload: "' oR 1=1#", verdict: "adapt · blocked", step: 5, color: C.amber },
  { payload: "'/**/OR/**/1=1--", verdict: "confirmed ✓", step: 8, color: C.green },
];

const Node: React.FC<{ readonly i: number; readonly active: boolean }> = ({ i, active }) => {
  const frame = useCurrentFrame();
  const p = interpolate(frame, [8 + i * 5, 22 + i * 5], [0, 1], { ...CLAMP, easing: EASE_OUT });
  const n = NODES[i];
  return (
    <div
      style={{
        position: "absolute",
        left: NODE_X[i],
        top: NODE_Y,
        width: NODE_W,
        height: NODE_H,
        padding: "20px 24px",
        borderRadius: 18,
        border: `3px solid ${active ? C.coral : C.line}`,
        backgroundColor: C.panel,
        boxShadow: active ? `0 0 50px ${C.coral}66` : "none",
        opacity: p,
        scale: 0.94 + p * 0.06,
        fontFamily: FONT_MONO,
      }}
    >
      <div style={{ fontSize: 38, fontWeight: 700, color: active ? C.coral : C.text, letterSpacing: 2 }}>{n.name}</div>
      <div style={{ fontSize: 22, color: "#22d3ee", marginTop: 8 }}>{n.model}</div>
      <div style={{ fontSize: 20, color: C.dim, marginTop: 8 }}>{n.role}</div>
    </div>
  );
};

export const Hypothesis: React.FC = () => {
  const frame = useCurrentFrame();
  const step = Math.min(SEQ.length - 1, Math.max(0, Math.floor((frame - FIRST) / STEP)));
  const active = frame >= FIRST ? SEQ[step] : -1;
  const adaptDraw = interpolate(frame, [60, 90], [0, 1], { ...CLAMP, easing: EASE_OUT });
  const panel = interpolate(frame, [40, 60], [0, 1], { ...CLAMP, easing: EASE_OUT });

  return (
    <AbsoluteFill>
      <div style={{ position: "absolute", left: 150, top: 96 }}>
        <Appear from={0}>
          <Eyebrow>DeepAgents reasoning</Eyebrow>
        </Appear>
        <Appear from={6} style={{ marginTop: 18 }}>
          <Headline size={78}>Hypothesize. Attack. Adapt.</Headline>
        </Appear>
      </div>

      <svg width={1920} height={1080} style={{ position: "absolute", inset: 0 }}>
        {[0, 1, 2].map((i) => (
          <FlowWire
            key={i}
            a={{ x: NODE_X[i] + NODE_W, y: MID_Y }}
            b={{ x: NODE_X[i + 1], y: MID_Y }}
            at={20 + i * 6}
            len={14}
            loop={frame >= FIRST}
          />
        ))}
        {/* adapt loop: MUTATE back to PROBE */}
        <path
          d={`M ${NODE_X[3] + NODE_W / 2} ${NODE_Y + NODE_H} C ${NODE_X[3] + NODE_W / 2} ${NODE_Y + NODE_H + 140}, ${NODE_X[1] + NODE_W / 2} ${NODE_Y + NODE_H + 140}, ${NODE_X[1] + NODE_W / 2} ${NODE_Y + NODE_H}`}
          fill="none"
          stroke={C.amber}
          strokeWidth={3}
          strokeDasharray="10 8"
          strokeOpacity={adaptDraw}
        />
      </svg>
      <div
        style={{
          position: "absolute",
          left: 0,
          width: 1920,
          top: NODE_Y + NODE_H + 130,
          textAlign: "center",
          fontFamily: FONT_MONO,
          fontSize: 24,
          color: C.amber,
          letterSpacing: 4,
          opacity: adaptDraw,
        }}
      >
        ADAPT · REPEAT
      </div>

      {NODES.map((_, i) => (
        <Node key={i} i={i} active={i === active} />
      ))}

      <div
        style={{
          position: "absolute",
          left: 150,
          right: 150,
          top: 700,
          height: 250,
          borderRadius: 18,
          border: `2px solid ${C.line}`,
          backgroundColor: `${C.panel}ee`,
          padding: "20px 32px",
          fontFamily: FONT_MONO,
          opacity: panel,
        }}
      >
        <div style={{ display: "flex", justifyContent: "space-between", fontSize: 22, color: C.dim }}>
          <span>hypothesis H1 · SQL injection · GET /api/orders?id=</span>
          <span>illustrative trace · up to 10 hypotheses per agent</span>
        </div>
        {TRACE.map((t) => {
          const at = FIRST + t.step * STEP + 6;
          const p = interpolate(frame, [at, at + 10], [0, 1], { ...CLAMP, easing: EASE_OUT });
          return (
            <div
              key={t.payload}
              style={{
                display: "flex",
                gap: 40,
                marginTop: 22,
                fontSize: 32,
                opacity: p,
                translate: `${(1 - p) * 30}px 0px`,
              }}
            >
              <span style={{ color: C.text, width: 560 }}>{t.payload}</span>
              <span style={{ color: t.color }}>→ {t.verdict}</span>
            </div>
          );
        })}
      </div>
    </AbsoluteFill>
  );
};
