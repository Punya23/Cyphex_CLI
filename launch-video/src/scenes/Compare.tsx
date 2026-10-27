import { AbsoluteFill, Easing, interpolate, useCurrentFrame } from "remotion";
import { Appear, Eyebrow, Headline } from "../components/kit";
import { C, CLAMP, FONT_MONO } from "../theme";

const EASE_OUT = Easing.bezier(0.215, 0.61, 0.355, 1); // power3.out

type Cell = { readonly mark: "yes" | "no" | "part"; readonly note?: string };
const Y: Cell = { mark: "yes" };
const N: Cell = { mark: "no" };

// Capability matrix from each tool's public scope (no invented scan numbers).
const TOOLS = ["Burp Suite", "OWASP ZAP", "Dependabot", "CYPHEX"] as const;
const ROWS: readonly { readonly label: string; readonly cells: readonly [Cell, Cell, Cell, Cell] }[] = [
  { label: "Finds web vulns (DAST)", cells: [Y, Y, N, Y] },
  { label: "Scans your source (SAST)", cells: [N, N, N, Y] },
  { label: "Flags vulnerable dependencies", cells: [N, N, Y, Y] },
  { label: "Writes the fix", cells: [N, N, { mark: "part", note: "version bumps" }, Y] },
  { label: "Proves the fix works", cells: [N, N, N, Y] },
  { label: "Blocks attacks at runtime", cells: [N, N, N, Y] },
  { label: "Runs fully on your machine", cells: [Y, Y, N, Y] },
  { label: "No licence or API key", cells: [{ mark: "part", note: "Pro is paid" }, Y, Y, Y] },
];

const LABEL_X = 150;
const COL_X = [740, 990, 1240, 1490];
const COL_W = [250, 250, 250, 280];
const HEAD_Y = 270;
const ROW_Y0 = 346;
const ROW_H = 56;

const MARK = { yes: { glyph: "✓", color: C.green }, no: { glyph: "✕", color: C.faint }, part: { glyph: "◐", color: C.amber } };

const Row: React.FC<{ readonly i: number }> = ({ i }) => {
  const frame = useCurrentFrame();
  const at = 22 + i * 14;
  const p = interpolate(frame, [at, at + 12], [0, 1], { ...CLAMP, easing: EASE_OUT });
  const row = ROWS[i];
  const y = ROW_Y0 + i * ROW_H;
  return (
    <div style={{ opacity: p, translate: `0px ${(1 - p) * 16}px` }}>
      <div style={{ position: "absolute", left: LABEL_X, top: y, fontFamily: FONT_MONO, fontSize: 27, color: C.text }}>
        {row.label}
      </div>
      {row.cells.map((c, j) => (
        <div
          key={TOOLS[j]}
          style={{
            position: "absolute",
            left: COL_X[j],
            top: y - 2,
            width: COL_W[j],
            textAlign: "center",
            fontFamily: FONT_MONO,
            fontSize: c.note ? 22 : 34,
            fontWeight: 700,
            color: MARK[c.mark].color,
            lineHeight: "36px",
          }}
        >
          {MARK[c.mark].glyph}
          {c.note ? ` ${c.note}` : ""}
        </div>
      ))}
      <div
        style={{
          position: "absolute",
          left: LABEL_X,
          width: COL_X[3] + COL_W[3] - LABEL_X,
          top: y + ROW_H - 12,
          height: 1,
          backgroundColor: C.line,
        }}
      />
    </div>
  );
};

export const Compare: React.FC = () => {
  const frame = useCurrentFrame();
  const head = interpolate(frame, [6, 20], [0, 1], { ...CLAMP, easing: EASE_OUT });
  const glow = interpolate(frame, [60, 90], [0, 1], CLAMP);
  const stats = interpolate(frame, [150, 170], [0, 1], { ...CLAMP, easing: EASE_OUT });

  return (
    <AbsoluteFill>
      <div style={{ position: "absolute", left: 150, top: 96 }}>
        <Appear from={0}>
          <Eyebrow>Side by side</Eyebrow>
        </Appear>
        <Appear from={6} style={{ marginTop: 18 }}>
          <Headline size={78}>Others find. CYPHEX proves.</Headline>
        </Appear>
      </div>

      {/* CYPHEX column highlight */}
      <div
        style={{
          position: "absolute",
          left: COL_X[3],
          top: HEAD_Y - 10,
          width: COL_W[3],
          height: ROW_Y0 + ROWS.length * ROW_H - HEAD_Y + 6,
          borderRadius: 18,
          border: `3px solid ${C.coral}`,
          backgroundColor: `${C.coral}12`,
          boxShadow: `0 0 ${50 * glow}px ${C.coral}55`,
          opacity: glow,
        }}
      />

      {TOOLS.map((t, j) => (
        <div
          key={t}
          style={{
            position: "absolute",
            left: COL_X[j],
            top: HEAD_Y,
            width: COL_W[j],
            textAlign: "center",
            fontFamily: FONT_MONO,
            fontWeight: 700,
            fontSize: 28,
            letterSpacing: 1,
            color: j === 3 ? C.coral : C.text,
            opacity: head,
          }}
        >
          {t}
        </div>
      ))}

      {ROWS.map((_, i) => (
        <Row key={i} i={i} />
      ))}

      <div style={{ position: "absolute", left: 150, right: 150, top: 840, opacity: stats, translate: `0px ${(1 - stats) * 20}px` }}>
        <div style={{ display: "flex", gap: 44, fontFamily: FONT_MONO, fontSize: 28, color: C.text, whiteSpace: "nowrap" }}>
          <span>
            <span style={{ color: C.coral, fontWeight: 700 }}>91.3%</span> recall
          </span>
          <span>
            <span style={{ color: C.coral, fontWeight: 700 }}>97.7%</span> precision
          </span>
          <span>
            <span style={{ color: C.coral, fontWeight: 700 }}>3.3%</span> false positives
          </span>
          <span>
            <span style={{ color: C.coral, fontWeight: 700 }}>100%</span> durable-verified patches
          </span>
        </div>
        <div style={{ fontFamily: FONT_MONO, fontSize: 19, color: C.dim, marginTop: 14, whiteSpace: "nowrap" }}>
          CYPHEX figures: own immune benchmark (76 samples) and 52 patch attempts · capability comparison, not a head-to-head scan test
        </div>
      </div>
    </AbsoluteFill>
  );
};
