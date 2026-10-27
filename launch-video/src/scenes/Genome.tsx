import { AbsoluteFill, Easing, interpolate, useCurrentFrame } from "remotion";
import { FlowWire } from "../components/FlowWire";
import { Appear, Eyebrow, Headline } from "../components/kit";
import { C, CLAMP, FONT_DISPLAY, FONT_MONO } from "../theme";

const EASE_OUT = Easing.bezier(0.215, 0.61, 0.355, 1); // power3.out

// How the genome .pkl is made, from the README's Behavioural Immune System.
const STAGES = [
  { title: "LEARN NORMAL", lines: ["20 endpoints profiled", "15 features per input", "entropy, length, etc."] },
  { title: "RED vs BLUE", lines: ["red mutates attacks", "blue retrains genome", "10 gens × 20 payloads"] },
  { title: "SIGNED .pkl", lines: ["genome_<target>.pkl", "HMAC-SHA256 sidecar", "key file mode 0600"] },
  { title: ".cxgenome", lines: ["one-file bundle", "export from scan host", "import on production"] },
];
const STAGE_W = 340;
const STAGE_X = [150, 570, 990, 1410];
const STAGE_Y = 330;
const STAGE_H = 230;

const FILES = [
  { name: "genome_a3f9c2.pkl", note: "trained model", color: C.green },
  { name: "genome_a3f9c2.pkl.hmac", note: "signature", color: C.green },
  { name: ".genome_hmac.key", note: "chmod 0600", color: C.amber },
  { name: "target.cxgenome", note: "portable bundle", color: C.coral },
];

const rise = (frame: number, at: number, len = 14): number =>
  interpolate(frame, [at, at + len], [0, 1], { ...CLAMP, easing: EASE_OUT });

const Stage: React.FC<{ readonly i: number }> = ({ i }) => {
  const frame = useCurrentFrame();
  const p = rise(frame, 8 + i * 26);
  const s = STAGES[i];
  return (
    <div
      style={{
        position: "absolute",
        left: STAGE_X[i],
        top: STAGE_Y,
        width: STAGE_W,
        height: STAGE_H,
        padding: "22px 26px",
        borderRadius: 18,
        border: `2px solid ${i === 2 ? C.coral : C.line}`,
        backgroundColor: C.panel,
        boxShadow: i === 2 ? `0 0 44px ${C.coral}44` : "none",
        opacity: p,
        scale: 0.94 + p * 0.06,
        fontFamily: FONT_MONO,
      }}
    >
      <div style={{ fontSize: 30, fontWeight: 700, color: i === 2 ? C.coral : C.text, letterSpacing: 2 }}>{s.title}</div>
      {s.lines.map((l) => (
        <div key={l} style={{ fontSize: 20, color: C.dim, marginTop: 12 }}>
          {l}
        </div>
      ))}
    </div>
  );
};

export const Genome: React.FC = () => {
  const frame = useCurrentFrame();
  const GEN_START = 110;
  const GEN_EVERY = 16;
  const gen = Math.min(7, Math.max(0, Math.floor((frame - GEN_START) / GEN_EVERY) + 1));
  const converged = frame >= GEN_START + 7 * GEN_EVERY;
  const phase = ((frame - GEN_START) % GEN_EVERY) / GEN_EVERY; // 0..1 within a generation
  const running = frame >= GEN_START && !converged;
  const red = running ? interpolate(phase, [0, 0.5, 1], [0.1, 1, 1], CLAMP) : converged ? 0.15 : 0;
  const blue = running ? interpolate(phase, [0.4, 1], [0.1, 1], CLAMP) : converged ? 1 : 0;
  const panelIn = rise(frame, 96);

  return (
    <AbsoluteFill>
      <div style={{ position: "absolute", left: 150, top: 96 }}>
        <Appear from={0}>
          <Eyebrow>The immune genome</Eyebrow>
        </Appear>
        <Appear from={6} style={{ marginTop: 18 }}>
          <Headline size={78}>It learns your app's normal.</Headline>
        </Appear>
      </div>

      <svg width={1920} height={1080} style={{ position: "absolute", inset: 0 }}>
        {[0, 1, 2].map((i) => (
          <FlowWire
            key={i}
            a={{ x: STAGE_X[i] + STAGE_W, y: STAGE_Y + STAGE_H / 2 }}
            b={{ x: STAGE_X[i + 1], y: STAGE_Y + STAGE_H / 2 }}
            at={28 + i * 26}
            len={16}
            loop={frame > 120}
          />
        ))}
      </svg>
      {STAGES.map((_, i) => (
        <Stage key={i} i={i} />
      ))}

      {/* co-evolution */}
      <div
        style={{
          position: "absolute",
          left: 150,
          top: 630,
          width: 860,
          height: 310,
          padding: "22px 30px",
          borderRadius: 18,
          border: `2px solid ${C.line}`,
          backgroundColor: `${C.panel}ee`,
          fontFamily: FONT_MONO,
          opacity: panelIn,
        }}
      >
        <div style={{ display: "flex", justifyContent: "space-between", fontSize: 22, color: C.dim }}>
          <span>adversarial co-evolution</span>
          <span>illustrative</span>
        </div>
        {[
          { label: "RED  attacks mutate", v: red, color: C.red },
          { label: "BLUE genome retrains", v: blue, color: "#22d3ee" },
        ].map((b) => (
          <div key={b.label} style={{ marginTop: 18 }}>
            <div style={{ fontSize: 24, color: C.text }}>{b.label}</div>
            <div style={{ marginTop: 10, height: 16, borderRadius: 8, backgroundColor: C.line }}>
              <div style={{ width: `${b.v * 100}%`, height: "100%", borderRadius: 8, backgroundColor: b.color }} />
            </div>
          </div>
        ))}
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", marginTop: 22 }}>
          <span style={{ fontSize: 20, color: converged ? C.green : C.dim }}>
            {converged ? "converged ✓ early-stop" : "early-stop at ≥ 99% block × 3 gens"}
          </span>
          <span style={{ fontFamily: FONT_DISPLAY, fontWeight: 700, fontSize: 64, color: C.coral }}>
            GEN {gen}
            <span style={{ fontSize: 34, color: C.faint }}>/10</span>
          </span>
        </div>
      </div>

      {/* what lands on disk */}
      <div style={{ position: "absolute", left: 1060, top: 630, width: 710, fontFamily: FONT_MONO }}>
        {FILES.map((f, i) => {
          const p = rise(frame, 140 + i * 18);
          return (
            <div
              key={f.name}
              style={{
                display: "flex",
                justifyContent: "space-between",
                padding: "16px 24px",
                marginBottom: 14,
                borderRadius: 14,
                border: `2px solid ${C.line}`,
                backgroundColor: C.panel,
                fontSize: 26,
                opacity: p,
                translate: `${(1 - p) * 40}px 0px`,
              }}
            >
              <span style={{ color: C.text }}>{f.name}</span>
              <span style={{ color: f.color }}>{f.note}</span>
            </div>
          );
        })}
      </div>
    </AbsoluteFill>
  );
};
