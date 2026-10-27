import { AbsoluteFill, Easing, interpolate, useCurrentFrame } from "remotion";
import { Appear, Eyebrow, Headline } from "../components/kit";
import { C, CLAMP, FONT_MONO } from "../theme";

const EASE_OUT = Easing.bezier(0.215, 0.61, 0.355, 1); // power3.out
const BLOCK_THRESHOLD = 0.7; // GENOME_BLOCK_THRESHOLD in the README

// Sample scores straight from the README's /search table (untrained genome).
const REQUESTS = [
  { payload: "normal search query", score: 0.0 },
  { payload: "' OR 1=1--", score: 1.0 },
  { payload: "{{7*7}}", score: 0.8 },
  { payload: "http://169.254.169.254/latest/meta-data/", score: 0.8 },
  { payload: "; cat /etc/passwd", score: 1.0 },
];
const ROW_Y0 = 300;
const ROW_GAP = 86;
const FIRST = 24;
const EVERY = 44;
const GATE_X = 880;

const startOf = (i: number): number => FIRST + i * EVERY;
const isBlocked = (score: number): boolean => score >= BLOCK_THRESHOLD;

const Row: React.FC<{ readonly i: number }> = ({ i }) => {
  const frame = useCurrentFrame();
  const { payload, score } = REQUESTS[i];
  const s = startOf(i);
  const blocked = isBlocked(score);
  const inP = interpolate(frame, [s, s + 10], [0, 1], { ...CLAMP, easing: EASE_OUT });
  const travel = interpolate(frame, [s + 8, s + 18], [0, 1], CLAMP);
  const shown = interpolate(frame, [s + 18, s + 30], [0, score], CLAMP);
  const pill = interpolate(frame, [s + 28, s + 36], [0, 1], { ...CLAMP, easing: EASE_OUT });
  const onward = interpolate(frame, [s + 34, s + 50], [0, 1], CLAMP);
  const color = blocked ? C.red : C.green;
  const y = ROW_Y0 + i * ROW_GAP;
  return (
    <>
      <div
        style={{
          position: "absolute",
          left: 150,
          top: y,
          width: 650,
          fontFamily: FONT_MONO,
          fontSize: 27,
          color: C.text,
          opacity: inP,
          translate: `${(1 - inP) * -30}px 0px`,
          whiteSpace: "nowrap",
        }}
      >
        {payload}
      </div>
      {/* request chip travelling to the gate, then on to the app if allowed */}
      {frame >= s + 8 && (blocked ? frame < s + 20 : true) ? (
        <div
          style={{
            position: "absolute",
            left: blocked ? 810 + travel * (GATE_X - 810) : 810 + travel * (GATE_X - 810) + onward * (1490 - GATE_X),
            top: y + 8,
            width: 18,
            height: 18,
            borderRadius: 9,
            backgroundColor: color,
            boxShadow: `0 0 16px ${color}`,
            opacity: blocked ? 1 - Math.max(0, (frame - (s + 18)) / 2) : 1 - Math.max(0, (onward - 0.9) * 10),
          }}
        />
      ) : null}
      <div
        style={{
          position: "absolute",
          left: 985,
          top: y - 2,
          fontFamily: FONT_MONO,
          fontSize: 32,
          fontWeight: 700,
          color: C.text,
          opacity: interpolate(frame, [s + 18, s + 22], [0, 1], CLAMP),
        }}
      >
        {shown.toFixed(2)}
      </div>
      <div
        style={{
          position: "absolute",
          left: 1130,
          top: y - 6,
          padding: "6px 18px",
          borderRadius: 10,
          border: `2px solid ${color}`,
          backgroundColor: `${color}1f`,
          fontFamily: FONT_MONO,
          fontWeight: 700,
          fontSize: 26,
          color,
          opacity: pill,
          scale: 0.9 + pill * 0.1,
        }}
      >
        {blocked ? "✕ BLOCK" : "✓ ALLOW"}
      </div>
    </>
  );
};

const Chip: React.FC<{
  readonly label: string;
  readonly tag: string;
  readonly color: string;
  readonly solid: boolean;
  readonly at: number;
  readonly x: number;
}> = ({ label, tag, color, solid, at, x }) => {
  const frame = useCurrentFrame();
  const p = interpolate(frame, [at, at + 14], [0, 1], { ...CLAMP, easing: EASE_OUT });
  return (
    <div
      style={{
        position: "absolute",
        left: x,
        top: 880,
        display: "flex",
        gap: 16,
        alignItems: "center",
        padding: "14px 26px",
        borderRadius: 14,
        border: `2px ${solid ? "solid" : "dashed"} ${color}`,
        backgroundColor: solid ? `${color}1f` : "transparent",
        fontFamily: FONT_MONO,
        fontSize: 26,
        color: solid ? C.text : C.dim,
        opacity: p,
        translate: `0px ${(1 - p) * 20}px`,
      }}
    >
      {label}
      <span style={{ fontSize: 18, letterSpacing: 3, color }}>{tag}</span>
    </div>
  );
};

export const DecisionGate: React.FC = () => {
  const frame = useCurrentFrame();
  // The gate flashes red the instant a blocked request reaches it.
  const flash = REQUESTS.reduce(
    (m, r, i) =>
      isBlocked(r.score)
        ? Math.max(m, interpolate(frame, [startOf(i) + 18, startOf(i) + 21, startOf(i) + 34], [0, 1, 0], CLAMP))
        : m,
    0,
  );
  const gateIn = interpolate(frame, [8, 24], [0, 1], { ...CLAMP, easing: EASE_OUT });
  const appGlow = REQUESTS.reduce(
    (m, r, i) =>
      isBlocked(r.score) ? m : Math.max(m, interpolate(frame, [startOf(i) + 46, startOf(i) + 52, startOf(i) + 70], [0, 1, 0], CLAMP)),
    0,
  );
  const callout = interpolate(frame, [215, 235], [0, 1], { ...CLAMP, easing: EASE_OUT });

  return (
    <AbsoluteFill>
      <div style={{ position: "absolute", left: 150, top: 96 }}>
        <Appear from={0}>
          <Eyebrow>Zero-day defence · the decision model</Eyebrow>
        </Appear>
        <Appear from={6} style={{ marginTop: 18 }}>
          <Headline size={78}>Unfair payloads don't pass.</Headline>
        </Appear>
      </div>

      {/* the gate */}
      <div
        style={{
          position: "absolute",
          left: GATE_X,
          top: 270,
          width: 24,
          height: 450,
          borderRadius: 12,
          backgroundColor: flash > 0.05 ? C.red : C.coral,
          boxShadow: `0 0 ${30 + flash * 70}px ${flash > 0.05 ? C.red : C.coral}`,
          opacity: gateIn,
        }}
      />
      <div
        style={{
          position: "absolute",
          left: GATE_X - 300,
          width: 624,
          top: 735,
          textAlign: "center",
          fontFamily: FONT_MONO,
          fontSize: 22,
          letterSpacing: 3,
          color: C.dim,
          opacity: gateIn,
        }}
      >
        GENOME DECISION MODEL · BLOCK ≥ 0.70
      </div>

      {/* your app */}
      <div
        style={{
          position: "absolute",
          left: 1490,
          top: 270,
          width: 280,
          height: 450,
          borderRadius: 18,
          border: `2px solid ${appGlow > 0.05 ? C.green : C.line}`,
          backgroundColor: C.panel,
          boxShadow: `0 0 ${appGlow * 60}px ${C.green}`,
          fontFamily: FONT_MONO,
          fontSize: 26,
          letterSpacing: 3,
          color: C.dim,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          opacity: gateIn,
        }}
      >
        YOUR APP
      </div>

      {REQUESTS.map((_, i) => (
        <Row key={i} i={i} />
      ))}

      <div
        style={{
          position: "absolute",
          left: 150,
          right: 150,
          top: 790,
          fontFamily: FONT_MONO,
          fontSize: 30,
          color: C.text,
          opacity: callout,
          translate: `0px ${(1 - callout) * 20}px`,
        }}
      >
        <span style={{ color: C.coral }}>Zero-day?</span> No signature needed. It scores behaviour, not rules.
      </div>

      <Chip label="● RASP guard · /watch" tag="TODAY" color={C.green} solid at={255} x={150} />
      <Chip label="○ AWS WAF" tag="PLANNED" color={C.amber} solid={false} at={270} x={720} />
      <Chip label="○ Cloudflare" tag="PLANNED" color={C.amber} solid={false} at={285} x={1060} />
    </AbsoluteFill>
  );
};
