import { AbsoluteFill, Easing, interpolate, useCurrentFrame } from "remotion";
import { Appear, Eyebrow, Headline } from "../components/kit";
import { C, CLAMP, FONT_DISPLAY, FONT_MONO } from "../theme";

const EASE_OUT = Easing.bezier(0.215, 0.61, 0.355, 1); // power3.out
const BLOCK_THRESHOLD = 0.7; // GENOME_BLOCK_THRESHOLD in the README

// Scores are the real ones: the genome scoring table in the recording (benign rows,
// ' OR 1=1--, SSRF, ; cat /etc/passwd) and the README's {{7*7}} sample.
const REQUESTS = [
  { payload: "laptop", score: 0.453 },
  { payload: "John O'Brien", score: 0.549 },
  { payload: "' OR 1=1--", score: 1.0 },
  { payload: "{{7*7}}", score: 0.8 },
  { payload: "http://169.254.169.254/latest/meta-data/", score: 1.0 },
  { payload: "; cat /etc/passwd", score: 1.0 },
];

const ROW_Y0 = 290;
const ROW_GAP = 84;
const FIRST = 14;
const EVERY = 26;
const TRACK_X = 800;
const TRACK_W = 600;
const THRESH_X = TRACK_X + BLOCK_THRESHOLD * TRACK_W;

const startOf = (i: number): number => FIRST + i * EVERY;
/** The decision model's output: one bit. */
const bitOf = (score: number): 0 | 1 => (score >= BLOCK_THRESHOLD ? 1 : 0);

const Row: React.FC<{ readonly i: number }> = ({ i }) => {
  const frame = useCurrentFrame();
  const { payload, score } = REQUESTS[i];
  const s = startOf(i);
  const bit = bitOf(score);
  const color = bit ? C.red : C.green;
  const y = ROW_Y0 + i * ROW_GAP;
  const inP = interpolate(frame, [s, s + 10], [0, 1], {
    ...CLAMP,
    easing: EASE_OUT,
  });
  const slide = interpolate(frame, [s + 6, s + 28], [0, 1], {
    ...CLAMP,
    easing: EASE_OUT,
  });
  const value = slide * score;
  const decided = interpolate(frame, [s + 28, s + 36], [0, 1], {
    ...CLAMP,
    easing: EASE_OUT,
  });
  return (
    <>
      <div
        style={{
          position: "absolute",
          left: 150,
          top: y,
          width: 630,
          fontFamily: FONT_MONO,
          fontSize: 24,
          color: C.text,
          opacity: inP,
          translate: `${(1 - inP) * -30}px 0px`,
          whiteSpace: "nowrap",
        }}
      >
        {payload}
      </div>
      <div
        style={{
          position: "absolute",
          left: TRACK_X,
          top: y + 8,
          width: TRACK_W,
          height: 14,
          borderRadius: 7,
          overflow: "hidden",
          opacity: inP,
        }}
      >
        <div
          style={{
            position: "absolute",
            left: 0,
            width: BLOCK_THRESHOLD * TRACK_W,
            height: "100%",
            backgroundColor: `${C.green}30`,
          }}
        />
        <div
          style={{
            position: "absolute",
            left: BLOCK_THRESHOLD * TRACK_W,
            right: 0,
            height: "100%",
            backgroundColor: `${C.red}40`,
          }}
        />
      </div>
      <div
        style={{
          position: "absolute",
          left: TRACK_X + value * TRACK_W - 12,
          top: y + 3,
          width: 24,
          height: 24,
          borderRadius: 12,
          backgroundColor: decided > 0.5 ? color : C.text,
          boxShadow: `0 0 ${14 + decided * 16}px ${decided > 0.5 ? color : C.text}`,
          opacity: inP,
        }}
      />
      <div
        style={{
          position: "absolute",
          left: TRACK_X + TRACK_W + 24,
          top: y - 2,
          fontFamily: FONT_MONO,
          fontSize: 28,
          fontWeight: 700,
          color: C.text,
          opacity: inP,
        }}
      >
        {value.toFixed(2)}
      </div>
      <div
        style={{
          position: "absolute",
          left: TRACK_X + TRACK_W + 130,
          top: y - 8,
          width: 52,
          height: 46,
          borderRadius: 10,
          border: `2px solid ${color}`,
          backgroundColor: `${color}22`,
          fontFamily: FONT_MONO,
          fontWeight: 700,
          fontSize: 32,
          color,
          textAlign: "center",
          lineHeight: "42px",
          opacity: decided,
          scale: 0.8 + decided * 0.2,
        }}
      >
        {bit}
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
  const p = interpolate(frame, [at, at + 14], [0, 1], {
    ...CLAMP,
    easing: EASE_OUT,
  });
  return (
    <div
      style={{
        position: "absolute",
        left: x,
        top: 900,
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
  const head = interpolate(frame, [4, 18], [0, 1], {
    ...CLAMP,
    easing: EASE_OUT,
  });

  // Output bit = verdict of the most recently decided request.
  const decidedCount = REQUESTS.reduce(
    (n, _, i) => (frame >= startOf(i) + 28 ? i + 1 : n),
    0,
  );
  const last =
    decidedCount > 0 ? bitOf(REQUESTS[decidedCount - 1].score) : null;
  const outColor = last === null ? C.faint : last ? C.red : C.green;
  const flip =
    decidedCount > 0
      ? interpolate(
          frame,
          [startOf(decidedCount - 1) + 28, startOf(decidedCount - 1) + 36],
          [0.6, 1],
          CLAMP,
        )
      : 1;
  const callout = interpolate(frame, [150, 170], [0, 1], {
    ...CLAMP,
    easing: EASE_OUT,
  });

  return (
    <AbsoluteFill>
      <div style={{ position: "absolute", left: 150, top: 96 }}>
        <Appear from={0}>
          <Eyebrow>Decision model · the genome gate</Eyebrow>
        </Appear>
        <Appear from={6} style={{ marginTop: 18 }}>
          <Headline size={78}>Behaviour in. One bit out.</Headline>
        </Appear>
      </div>

      {/* axis labels + threshold */}
      <div
        style={{
          position: "absolute",
          left: TRACK_X,
          top: 252,
          width: TRACK_W,
          fontFamily: FONT_MONO,
          fontSize: 20,
          color: C.dim,
          opacity: head,
        }}
      >
        <span style={{ position: "absolute", left: 0 }}>0.0 · normal</span>
        <span style={{ position: "absolute", right: 0 }}>1.0 · attack</span>
        <span
          style={{
            position: "absolute",
            left: BLOCK_THRESHOLD * TRACK_W - 62,
            top: -30,
            color: C.coral,
            fontWeight: 700,
          }}
        >
          BLOCK ≥ 0.70
        </span>
      </div>
      <div
        style={{
          position: "absolute",
          left: THRESH_X - 1,
          top: 284,
          width: 3,
          height: ROW_GAP * REQUESTS.length - 14,
          backgroundColor: C.coral,
          boxShadow: `0 0 14px ${C.coral}`,
          opacity: head,
        }}
      />

      {REQUESTS.map((_, i) => (
        <Row key={i} i={i} />
      ))}

      {/* the one-bit output */}
      <div
        style={{
          position: "absolute",
          left: 1660,
          top: 290,
          width: 190,
          height: 380,
          borderRadius: 18,
          border: `3px solid ${outColor}`,
          backgroundColor: C.panel,
          boxShadow: `0 0 50px ${outColor}55`,
          textAlign: "center",
          fontFamily: FONT_MONO,
          opacity: head,
        }}
      >
        <div
          style={{
            fontSize: 20,
            letterSpacing: 4,
            color: C.dim,
            marginTop: 20,
          }}
        >
          OUTPUT
        </div>
        <div
          style={{
            fontFamily: FONT_DISPLAY,
            fontWeight: 700,
            fontSize: 190,
            lineHeight: 1.05,
            color: outColor,
            scale: flip,
            marginTop: 10,
          }}
        >
          {last === null ? "–" : last}
        </div>
        <div style={{ fontSize: 24, fontWeight: 700, color: outColor }}>
          {last === null ? "" : last ? "BLOCK" : "ALLOW"}
        </div>
        <div
          style={{ fontSize: 16, color: C.dim, marginTop: 22, lineHeight: 1.5 }}
        >
          0 = allow
          <br />1 = block
        </div>
      </div>

      <div
        style={{
          position: "absolute",
          left: 150,
          top: 815,
          fontFamily: FONT_MONO,
          fontSize: 30,
          color: C.text,
          opacity: callout,
          translate: `0px ${(1 - callout) * 20}px`,
        }}
      >
        <span style={{ color: C.coral }}>Zero-day?</span> No signature. 15
        behaviour features → score → one bit.
      </div>

      <Chip
        label="● RASP guard · /watch"
        tag="TODAY"
        color={C.green}
        solid
        at={172}
        x={150}
      />
      <Chip
        label="○ AWS WAF"
        tag="PLANNED"
        color={C.amber}
        solid={false}
        at={186}
        x={720}
      />
      <Chip
        label="○ Cloudflare"
        tag="PLANNED"
        color={C.amber}
        solid={false}
        at={200}
        x={1060}
      />
    </AbsoluteFill>
  );
};
