import { AbsoluteFill, Easing, interpolate, useCurrentFrame } from "remotion";
import { Appear, Eyebrow } from "../components/kit";
import { C, CLAMP, FONT_DISPLAY, FONT_MONO } from "../theme";

const EASE_OUT = Easing.bezier(0.16, 1, 0.3, 1);

const STATS = [
  { n: "13", label: "agents" },
  { n: "5", label: "checks" },
  { n: "3", label: "verdicts" },
  { n: "0", label: "API keys" },
];

const Line: React.FC<{
  readonly at: number;
  readonly children: string;
  readonly color?: string;
}> = ({ at, children, color = C.text }) => {
  const frame = useCurrentFrame();
  const p = interpolate(frame, [at, at + 14], [0, 1], {
    ...CLAMP,
    easing: EASE_OUT,
  });
  return (
    <div style={{ opacity: p, translate: `0px ${(1 - p) * 40}px`, color }}>
      {children}
    </div>
  );
};

const Stat: React.FC<{
  readonly n: string;
  readonly label: string;
  readonly i: number;
}> = ({ n, label, i }) => {
  const frame = useCurrentFrame();
  const at = 80 + i * 8;
  const p = interpolate(frame, [at, at + 12], [0, 1], {
    ...CLAMP,
    easing: EASE_OUT,
  });
  return (
    <div
      style={{
        opacity: p,
        scale: 0.9 + p * 0.1,
        padding: "22px 40px",
        borderRadius: 18,
        border: `2px solid ${C.line}`,
        backgroundColor: C.panel,
        textAlign: "center",
      }}
    >
      <div
        style={{
          fontFamily: FONT_DISPLAY,
          fontWeight: 700,
          fontSize: 84,
          color: C.coral,
          lineHeight: 1,
        }}
      >
        {n}
      </div>
      <div
        style={{
          fontFamily: FONT_MONO,
          fontSize: 24,
          color: C.dim,
          marginTop: 6,
        }}
      >
        {label}
      </div>
    </div>
  );
};

export const LocalFirst: React.FC = () => (
  <AbsoluteFill>
    <div style={{ position: "absolute", left: 150, top: 96 }}>
      <Appear from={0}>
        <Eyebrow>Local-first</Eyebrow>
      </Appear>
    </div>
    <div
      style={{
        position: "absolute",
        left: 150,
        right: 150,
        top: 210,
        fontFamily: FONT_DISPLAY,
        fontWeight: 700,
        fontSize: 108,
        letterSpacing: -3,
        lineHeight: 1.08,
      }}
    >
      <Line at={6}>Runs on your machine.</Line>
      <Line at={22} color={C.dim}>
        Local LLMs via Ollama.
      </Line>
      <Line at={38} color={C.dim}>
        Docker sandbox.
      </Line>
      <Line at={54} color={C.coral}>
        No cloud. No API keys. No billing.
      </Line>
    </div>
    <div
      style={{
        position: "absolute",
        left: 150,
        right: 150,
        top: 760,
        display: "flex",
        gap: 28,
      }}
    >
      {STATS.map((s, i) => (
        <Stat key={s.label} {...s} i={i} />
      ))}
    </div>
  </AbsoluteFill>
);
