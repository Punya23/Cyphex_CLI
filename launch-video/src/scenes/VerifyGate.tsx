import { AbsoluteFill, Easing, interpolate, useCurrentFrame } from "remotion";
import { Appear, Eyebrow, Headline } from "../components/kit";
import { C, CLAMP, FONT_MONO } from "../theme";

const EASE_OUT = Easing.bezier(0.16, 1, 0.3, 1);

const CHECKS = [
  "finding gone on re-scan",
  "file still compiles",
  "no suppression comments",
  "≤ 70% of lines deleted",
  "blast radius scaled to severity",
];

const CASES = [
  {
    verdict: "PASS",
    note: "re-scan clean · fix kept",
    color: C.green,
    at: 130,
  },
  { verdict: "FAIL", note: "rolled back automatically", color: C.red, at: 160 },
  {
    verdict: "UNVERIFIABLE",
    note: "never rounded up to PASS",
    color: C.amber,
    at: 190,
  },
];

const CheckRow: React.FC<{ readonly label: string; readonly i: number }> = ({
  label,
  i,
}) => {
  const frame = useCurrentFrame();
  const at = 70 + i * 9;
  const p = interpolate(frame, [at, at + 8], [0, 1], {
    ...CLAMP,
    easing: EASE_OUT,
  });
  return (
    <div
      style={{
        opacity: p,
        translate: `${(1 - p) * 30}px 0px`,
        fontFamily: FONT_MONO,
        fontSize: 30,
        color: C.text,
        display: "flex",
        gap: 18,
        marginBottom: 16,
      }}
    >
      <span style={{ color: C.green }}>✓</span>
      {label}
    </div>
  );
};

const Diff: React.FC = () => {
  const frame = useCurrentFrame();
  const p = interpolate(frame, [18, 34], [0, 1], {
    ...CLAMP,
    easing: EASE_OUT,
  });
  const fixed = interpolate(frame, [48, 58], [0, 1], CLAMP);
  const line = (bg: string, fg: string, sign: string, text: string, o = 1) => (
    <div
      style={{
        background: bg,
        color: fg,
        padding: "6px 22px",
        opacity: o,
        whiteSpace: "pre",
      }}
    >
      {sign} {text}
    </div>
  );
  return (
    <div
      style={{
        opacity: p,
        translate: `0px ${(1 - p) * 30}px`,
        borderRadius: 18,
        border: `2px solid ${C.line}`,
        backgroundColor: C.panel,
        overflow: "hidden",
        fontFamily: FONT_MONO,
        fontSize: 26,
        width: 960,
      }}
    >
      <div
        style={{
          padding: "10px 22px",
          color: C.dim,
          borderBottom: `2px solid ${C.line}`,
        }}
      >
        routes/orders.js
      </div>
      {line(
        "#f0524d1f",
        C.red,
        "−",
        'db.query("SELECT * FROM orders WHERE id=" + id)',
        1 - fixed * 0.55,
      )}
      {line(
        "#22c55e1f",
        C.green,
        "+",
        'db.query("SELECT * FROM orders WHERE id=?", [id])',
        fixed,
      )}
    </div>
  );
};

const Case: React.FC<{ readonly c: (typeof CASES)[number] }> = ({ c }) => {
  const frame = useCurrentFrame();
  const p = interpolate(frame, [c.at, c.at + 14], [0, 1], {
    ...CLAMP,
    easing: EASE_OUT,
  });
  return (
    <div
      style={{
        opacity: p,
        scale: 0.9 + p * 0.1,
        flex: 1,
        padding: "26px 30px",
        borderRadius: 18,
        border: `3px solid ${c.color}`,
        backgroundColor: `${c.color}14`,
        boxShadow: `0 0 50px ${c.color}33`,
      }}
    >
      <div
        style={{
          fontFamily: FONT_MONO,
          fontWeight: 700,
          fontSize: 40,
          color: c.color,
        }}
      >
        {c.verdict}
      </div>
      <div
        style={{
          fontFamily: FONT_MONO,
          fontSize: 24,
          color: C.dim,
          marginTop: 8,
        }}
      >
        {c.note}
      </div>
    </div>
  );
};

export const VerifyGate: React.FC = () => {
  const frame = useCurrentFrame();
  const endLine = interpolate(frame, [236, 252], [0, 1], {
    ...CLAMP,
    easing: EASE_OUT,
  });
  return (
    <AbsoluteFill>
      <div style={{ position: "absolute", left: 150, top: 96 }}>
        <Appear from={0}>
          <Eyebrow>The Verify Gate</Eyebrow>
        </Appear>
        <Appear from={6} style={{ marginTop: 18 }}>
          <Headline size={78}>A patch only counts if it survives.</Headline>
        </Appear>
      </div>

      <div style={{ position: "absolute", left: 150, top: 330 }}>
        <Diff />
      </div>

      <div style={{ position: "absolute", left: 1180, top: 330 }}>
        {CHECKS.map((c, i) => (
          <CheckRow key={c} label={c} i={i} />
        ))}
      </div>

      <div
        style={{
          position: "absolute",
          left: 150,
          right: 150,
          top: 650,
          display: "flex",
          gap: 28,
        }}
      >
        {CASES.map((c) => (
          <Case key={c.verdict} c={c} />
        ))}
      </div>

      <div
        style={{
          position: "absolute",
          left: 150,
          right: 150,
          top: 900,
          fontFamily: FONT_MONO,
          fontSize: 38,
          color: C.amber,
          opacity: endLine,
          translate: `0px ${(1 - endLine) * 20}px`,
        }}
      >
        UNVERIFIABLE is never rounded up to PASS.
      </div>
    </AbsoluteFill>
  );
};
