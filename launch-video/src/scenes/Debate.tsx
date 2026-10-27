import { AbsoluteFill, Easing, interpolate, useCurrentFrame } from "remotion";
import { FlowWire } from "../components/FlowWire";
import { Appear, Eyebrow, Headline } from "../components/kit";
import { C, CLAMP, FONT_DISPLAY, FONT_MONO } from "../theme";

const EASE_OUT = Easing.bezier(0.215, 0.61, 0.355, 1); // power3.out
const CYAN = "#22d3ee";

// Roles and models from the README's council + Local AI tables.
const PATCHER = { x: 150, y: 330, w: 400, h: 150 };
const PATCH = { x: 660, y: 330, w: 560, h: 150 };
const VALIDATORS = [
  { y: 330, model: "llama3.1:8b", vote: "✓ APPROVE", at: 110 },
  { y: 500, model: "deepseek-coder:6.7b", vote: "✓ APPROVE", at: 126 },
];
const VAL_X = 1330;
const VAL_W = 440;
const VAL_H = 140;

const useRise = (at: number, len = 14): number => {
  const frame = useCurrentFrame();
  return interpolate(frame, [at, at + len], [0, 1], { ...CLAMP, easing: EASE_OUT });
};

const Card: React.FC<{
  readonly x: number;
  readonly y: number;
  readonly w: number;
  readonly h: number;
  readonly at: number;
  readonly children: React.ReactNode;
  readonly glow?: string;
}> = ({ x, y, w, h, at, children, glow }) => {
  const p = useRise(at);
  return (
    <div
      style={{
        position: "absolute",
        left: x,
        top: y,
        width: w,
        height: h,
        padding: "20px 26px",
        borderRadius: 18,
        border: `2px solid ${glow ?? C.line}`,
        backgroundColor: C.panel,
        boxShadow: glow ? `0 0 40px ${glow}55` : "none",
        opacity: p,
        scale: 0.94 + p * 0.06,
        fontFamily: FONT_MONO,
      }}
    >
      {children}
    </div>
  );
};

const Outcome: React.FC<{
  readonly label: string;
  readonly color: string;
  readonly on: boolean;
  readonly x: number;
}> = ({ label, color, on, x }) => (
  <div
    style={{
      position: "absolute",
      left: x,
      top: 700,
      padding: "18px 34px",
      borderRadius: 14,
      border: `3px solid ${on ? color : C.line}`,
      backgroundColor: on ? `${color}1f` : "transparent",
      boxShadow: on ? `0 0 50px ${color}55` : "none",
      fontFamily: FONT_MONO,
      fontWeight: 700,
      fontSize: on ? 40 : 28,
      color: on ? color : C.faint,
    }}
  >
    {label}
  </div>
);

export const Debate: React.FC = () => {
  const frame = useCurrentFrame();
  const verdict = useRise(150);
  const factCheck = useRise(190);
  const badge = useRise(205, 18);
  const on = frame >= 150;

  return (
    <AbsoluteFill>
      <div style={{ position: "absolute", left: 150, top: 96 }}>
        <Appear from={0}>
          <Eyebrow>Patching · multi-model council</Eyebrow>
        </Appear>
        <Appear from={6} style={{ marginTop: 18 }}>
          <Headline size={78}>No API key. Models that argue.</Headline>
        </Appear>
      </div>

      <svg width={1920} height={1080} style={{ position: "absolute", inset: 0 }}>
        <FlowWire a={{ x: PATCHER.x + PATCHER.w, y: 405 }} b={{ x: PATCH.x, y: 405 }} at={24} len={16} />
        {VALIDATORS.map((v, i) => (
          <FlowWire
            key={v.model}
            a={{ x: PATCH.x + PATCH.w, y: 405 }}
            b={{ x: VAL_X, y: v.y + VAL_H / 2 }}
            at={70 + i * 8}
            len={22}
            color={CYAN}
          />
        ))}
      </svg>

      <Card x={PATCHER.x} y={PATCHER.y} w={PATCHER.w} h={PATCHER.h} at={8}>
        <div style={{ fontSize: 30, fontWeight: 700, color: C.coral, letterSpacing: 2 }}>PATCHER</div>
        <div style={{ fontSize: 26, color: CYAN, marginTop: 8 }}>qwen2.5-coder:7b</div>
        <div style={{ fontSize: 22, color: C.dim, marginTop: 6 }}>proposes the fix</div>
      </Card>

      <Card x={PATCH.x} y={PATCH.y} w={PATCH.w} h={PATCH.h} at={34}>
        <div style={{ fontSize: 20, color: C.dim }}>proposed patch · routes/orders.js</div>
        <div style={{ fontSize: 24, color: C.red, marginTop: 14, whiteSpace: "pre" }}>− query("…WHERE id=" + id)</div>
        <div style={{ fontSize: 24, color: C.green, marginTop: 6, whiteSpace: "pre" }}>+ query("…WHERE id=?", [id])</div>
      </Card>

      {VALIDATORS.map((v) => (
        <Card key={v.model} x={VAL_X} y={v.y} w={VAL_W} h={VAL_H} at={64} glow={frame >= v.at ? C.green : undefined}>
          <div style={{ fontSize: 26, fontWeight: 700, color: C.text, letterSpacing: 2 }}>VALIDATOR</div>
          <div style={{ fontSize: 24, color: CYAN, marginTop: 6 }}>{v.model}</div>
          <div
            style={{
              fontSize: 28,
              fontWeight: 700,
              color: C.green,
              marginTop: 8,
              opacity: interpolate(frame, [v.at, v.at + 8], [0, 1], CLAMP),
            }}
          >
            {v.vote}
          </div>
        </Card>
      ))}

      <div style={{ opacity: verdict }}>
        <Outcome label="CONFIRMED ✓" color={C.green} on={on} x={150} />
        <Outcome label="sent back" color={C.amber} on={false} x={620} />
        <Outcome label="dropped · false positive" color={C.red} on={false} x={900} />
      </div>

      <div
        style={{
          position: "absolute",
          left: 150,
          top: 830,
          fontFamily: FONT_MONO,
          fontSize: 26,
          color: C.dim,
          opacity: factCheck,
        }}
      >
        fact-check pass · a second model re-reads the report for invented findings
      </div>

      <div
        style={{
          position: "absolute",
          right: 150,
          top: 690,
          textAlign: "right",
          opacity: badge,
          translate: `0px ${(1 - badge) * 24}px`,
        }}
      >
        <div style={{ fontFamily: FONT_DISPLAY, fontWeight: 700, fontSize: 96, lineHeight: 1, color: C.coral, letterSpacing: -3 }}>
          0 API keys
        </div>
        <div style={{ fontFamily: FONT_MONO, fontSize: 24, color: C.dim, marginTop: 8 }}>100% local · Ollama</div>
      </div>
    </AbsoluteFill>
  );
};
