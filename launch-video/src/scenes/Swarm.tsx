import { AbsoluteFill, Easing, interpolate, useCurrentFrame } from "remotion";
import { Appear, Eyebrow, Headline } from "../components/kit";
import { C, CLAMP, FONT_DISPLAY, FONT_MONO } from "../theme";

const EASE_OUT = Easing.bezier(0.16, 1, 0.3, 1);

// The 13 DeepAgents, in their real execution groups (sequential groups).
const GROUPS: { label: string; agents: string[] }[] = [
  { label: "GROUP 1", agents: ["SQL Injection", "XSS", "Auth Bypass"] },
  { label: "GROUP 2", agents: ["Path Traversal", "Command Injection", "SSRF", "IDOR", "SSTI", "XXE"] },
  { label: "GROUP 3", agents: ["Business Logic"] },
  { label: "GROUP 4", agents: ["Prompt Injection", "Race Condition", "Mass Assignment"] },
];

const FIRST = 20;
const GAP = 14;

const Agent: React.FC<{ readonly name: string; readonly order: number }> = ({ name, order }) => {
  const frame = useCurrentFrame();
  const at = FIRST + order * GAP;
  const p = interpolate(frame, [at, at + 12], [0, 1], { ...CLAMP, easing: EASE_OUT });
  const seen = interpolate(frame, [at + 8, at + 24], [0, 1], CLAMP);
  const live = frame >= at && frame < at + 30;
  const color = seen > 0.5 ? C.green : C.coral;
  return (
    <div
      style={{
        opacity: 0.25 + p * 0.75,
        scale: 0.94 + p * 0.06,
        display: "flex",
        alignItems: "center",
        gap: 14,
        padding: "14px 22px",
        borderRadius: 14,
        border: `2px solid ${p > 0.1 ? color : C.line}`,
        backgroundColor: C.panel,
        boxShadow: live ? `0 0 36px ${C.coral}88` : "none",
        fontFamily: FONT_MONO,
        fontSize: 30,
        color: p > 0.1 ? C.text : C.faint,
      }}
    >
      <span style={{ color: p > 0.1 ? color : C.faint }}>{seen > 0.5 ? "✓" : "●"}</span>
      {name}
    </div>
  );
};

export const Swarm: React.FC = () => {
  const frame = useCurrentFrame();
  const count = Math.min(13, Math.max(0, Math.floor((frame - FIRST - 20) / GAP) + 1));

  let order = 0;
  return (
    <AbsoluteFill>
      <div style={{ position: "absolute", left: 150, top: 96 }}>
        <Appear from={0}>
          <Eyebrow>--deep · the swarm</Eyebrow>
        </Appear>
        <Appear from={6} style={{ marginTop: 18 }}>
          <Headline size={78}>13 specialist agents. One target.</Headline>
        </Appear>
      </div>

      <div style={{ position: "absolute", left: 150, right: 150, top: 340, display: "flex", flexDirection: "column", gap: 30 }}>
        {GROUPS.map((g) => (
          <div key={g.label} style={{ display: "flex", alignItems: "center", gap: 26 }}>
            <div style={{ width: 150, fontFamily: FONT_MONO, fontSize: 24, color: C.violet, letterSpacing: 3 }}>{g.label}</div>
            <div style={{ display: "flex", flexWrap: "wrap", gap: 18 }}>
              {g.agents.map((a) => (
                <Agent key={a} name={a} order={order++} />
              ))}
            </div>
          </div>
        ))}
      </div>

      <div style={{ position: "absolute", right: 150, bottom: 90, textAlign: "right" }}>
        <div style={{ fontFamily: FONT_DISPLAY, fontWeight: 700, fontSize: 150, color: C.coral, lineHeight: 1, letterSpacing: -4 }}>
          {count}
          <span style={{ color: C.faint, fontSize: 80 }}>/13</span>
        </div>
        <div style={{ fontFamily: FONT_MONO, fontSize: 26, color: C.dim, marginTop: 8 }}>agents dispatched · sample run: vibemart</div>
      </div>
    </AbsoluteFill>
  );
};
