import { AbsoluteFill, interpolate, useCurrentFrame } from "remotion";
import { Cursor, TerminalWindow, TypeText } from "../components/kit";
import { C, CLAMP, FONT_MONO } from "../theme";

const COMMAND = "cx deep ./vibemart";

// Real phase names from CYPHEX's waypoint trace.
const PHASES = [
  "GETTING SOURCE CODE",
  "STATIC CODE ANALYSIS",
  "DEPLOYING SANDBOX",
  "DYNAMIC VULNERABILITY SCAN",
  "IMMUNE SYSTEM - BUILD GENOME",
  "AI ATTACK SIMULATION",
  "SECURITY REPORT",
  "AI PATCH GENERATION",
  "VERIFY + SECURITY SCORE",
  "COMPLETE",
];

const PhaseLine: React.FC<{ readonly index: number; readonly at: number }> = ({
  index,
  at,
}) => {
  const frame = useCurrentFrame();
  const p = interpolate(frame, [at, at + 6], [0, 1], CLAMP);
  const last = index === PHASES.length - 1;
  return (
    <div
      style={{
        display: "flex",
        gap: 24,
        fontFamily: FONT_MONO,
        fontSize: 34,
        lineHeight: 1.5,
        opacity: p,
        translate: `${(1 - p) * -24}px 0px`,
        color: last ? C.green : C.text,
      }}
    >
      <span style={{ color: C.green }}>✓</span>
      <span style={{ color: C.violet }}>
        {String(index + 1).padStart(2, "0")}/10
      </span>
      <span style={{ fontWeight: last ? 700 : 400 }}>{PHASES[index]}</span>
    </div>
  );
};

export const ColdOpen: React.FC = () => {
  const frame = useCurrentFrame();

  const windowIn = interpolate(frame, [0, 14], [0, 1], CLAMP);
  const flash = interpolate(frame, [96, 104, 118], [0, 0.9, 0], CLAMP);

  return (
    <AbsoluteFill style={{ alignItems: "center", justifyContent: "center" }}>
      <div style={{ opacity: windowIn, scale: 0.94 + windowIn * 0.06 }}>
        <TerminalWindow title="cyphex — zsh" width={1560} height={860}>
          <div
            style={{
              fontFamily: FONT_MONO,
              fontSize: 60,
              fontWeight: 500,
              color: C.text,
              marginBottom: 28,
              height: 76,
            }}
          >
            <span style={{ color: C.coral }}>$ </span>
            <TypeText text={COMMAND} from={10} charsPerFrame={0.55} />
            <Cursor size={56} />
          </div>
          <div style={{ marginTop: 24 }}>
            {PHASES.map((_, i) => (
              <PhaseLine key={i} index={i} at={50 + i * 4.4} />
            ))}
          </div>
        </TerminalWindow>
      </div>
      <AbsoluteFill style={{ backgroundColor: C.coral, opacity: flash }} />
    </AbsoluteFill>
  );
};
