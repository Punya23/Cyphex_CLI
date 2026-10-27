import { AbsoluteFill, Easing, interpolate, useCurrentFrame } from "remotion";
import { Appear, Eyebrow, Headline } from "../components/kit";
import { C, CLAMP, FONT_DISPLAY, FONT_MONO } from "../theme";

const EASE_OUT = Easing.bezier(0.16, 1, 0.3, 1);

// Phase names are the real ones from CYPHEX's waypoint trace.
const PHASES = [
  { name: "Get the source", goal: "Acquire the target's source and identify what it is built with", out: "✓ detect framework   Node.js (Express) · 9 files" },
  { name: "Static code analysis", goal: "Find candidate weaknesses in the code without running it", out: "✓ scan source files   8 files" },
  { name: "Deploy the sandbox", goal: "Stand the app up in an isolated sandbox so it can be attacked safely", out: "✓ isolated container up   localhost sandbox" },
  { name: "Dynamic vulnerability scan", goal: "Prove which candidates are actually reachable and exploitable", out: "✓ crawl surface   9 pages · 15 live endpoints" },
  { name: "Build the immune genome", goal: "Learn this app's normal behaviour well enough to spot an attack", out: "✓ genome built   20 endpoints profiled" },
  { name: "Attack the genome", goal: "Attack the hardened genome to measure what it actually blocks", out: "DEFENSE RATE 7/8 (88%)   FALSE POSITIVES 0" },
  { name: "Security report", goal: "Turn confirmed findings into a report a human can act on", out: "✓ council validates findings vs false positives" },
  { name: "AI patch generation", goal: "Generate a fix for each confirmed finding and prove it works", out: "RAG · LLM · Reflexion · Memory" },
  { name: "Verify + score", goal: "Council review, then the Verify Gate decides what counts", out: "PASS · FAIL · UNVERIFIABLE" },
  { name: "Complete", goal: "A visual report of what was found, fixed, and proven", out: "10/10 COMPLETE" },
];

const START = 22;
const PER = 22;
const RAIL_L = 150;
const RAIL_W = 1620;
const STEP = RAIL_W / 9;

const currentIndex = (frame: number): number =>
  Math.min(9, Math.max(0, Math.floor((frame - START) / PER)));

const Node: React.FC<{ readonly i: number }> = ({ i }) => {
  const frame = useCurrentFrame();
  const active = currentIndex(frame);
  const started = frame >= START;
  const done = started && i < active;
  const isActive = started && i === active;
  const pop = interpolate(frame, [START + i * PER, START + i * PER + 10], [0, 1], {
    ...CLAMP,
    easing: EASE_OUT,
  });
  const color = done ? C.green : isActive ? C.coral : C.faint;
  const size = isActive ? 64 + pop * 12 : 52;
  return (
    <div
      style={{
        position: "absolute",
        left: RAIL_L + i * STEP - size / 2,
        top: 40 - size / 2,
        width: size,
        height: size,
        borderRadius: size / 2,
        backgroundColor: done ? `${C.green}22` : C.panel,
        border: `3px solid ${color}`,
        boxShadow: isActive ? `0 0 50px ${C.coral}aa` : done ? `0 0 20px ${C.green}44` : "none",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        fontFamily: FONT_MONO,
        fontWeight: 700,
        fontSize: 24,
        color,
      }}
    >
      {done ? "✓" : i + 1}
    </div>
  );
};

const PhaseCard: React.FC = () => {
  const frame = useCurrentFrame();
  const i = currentIndex(frame);
  const local = frame - START - i * PER;
  const p = interpolate(local, [0, 9], [0, 1], { ...CLAMP, easing: EASE_OUT });
  const phase = PHASES[i];
  const intro = interpolate(frame, [START - 6, START + 6], [0, 1], CLAMP);

  return (
    <div
      style={{
        opacity: intro,
        display: "flex",
        gap: 80,
        alignItems: "center",
        padding: "0 70px",
        height: 470,
        borderRadius: 28,
        border: `2px solid ${C.line}`,
        backgroundColor: `${C.panel}ee`,
        boxShadow: `0 40px 120px #000b, inset 0 0 120px ${C.coral}0d`,
      }}
    >
      <div
        style={{
          fontFamily: FONT_MONO,
          fontWeight: 700,
          fontSize: 230,
          letterSpacing: -10,
          color: C.violet,
          translate: `${(1 - p) * -40}px 0px`,
          lineHeight: 1,
          minWidth: 520,
        }}
      >
        {String(i + 1).padStart(2, "0")}
        <span style={{ color: C.faint, fontSize: 110, letterSpacing: -4 }}>/10</span>
      </div>
      <div style={{ opacity: p, translate: `${(1 - p) * 60}px 0px`, flex: 1 }}>
        <div
          style={{
            fontFamily: FONT_DISPLAY,
            fontWeight: 700,
            fontSize: 84,
            letterSpacing: -2,
            color: C.text,
            lineHeight: 1.05,
          }}
        >
          {phase.name}
        </div>
        <div style={{ fontFamily: FONT_MONO, fontSize: 32, lineHeight: 1.45, color: C.dim, marginTop: 26 }}>
          <span style={{ color: C.coral }}>goal ▸ </span>
          {phase.goal}
        </div>
        <div
          style={{
            marginTop: 34,
            fontFamily: FONT_MONO,
            fontSize: 28,
            color: C.green,
            backgroundColor: "#000a",
            border: `2px solid ${C.line}`,
            borderRadius: 14,
            padding: "16px 24px",
            display: "inline-block",
          }}
        >
          {phase.out}
        </div>
      </div>
    </div>
  );
};

export const Pipeline: React.FC = () => {
  const frame = useCurrentFrame();
  const fill = interpolate(frame, [START, START + 10 * PER], [0, 1], CLAMP);

  return (
    <AbsoluteFill>
      <div style={{ position: "absolute", left: 150, top: 96 }}>
        <Appear from={0}>
          <Eyebrow>One command · ten phases</Eyebrow>
        </Appear>
        <Appear from={6} style={{ marginTop: 18 }}>
          <Headline size={78}>Every phase has a goal.</Headline>
        </Appear>
      </div>

      <div style={{ position: "absolute", left: 0, top: 320, width: 1920, height: 80 }}>
        <div style={{ position: "absolute", left: RAIL_L, top: 38, width: RAIL_W, height: 4, backgroundColor: C.line, borderRadius: 2 }} />
        <div
          style={{
            position: "absolute",
            left: RAIL_L,
            top: 38,
            width: RAIL_W * fill,
            height: 4,
            background: `linear-gradient(90deg, ${C.green}, ${C.coral})`,
            borderRadius: 2,
            boxShadow: `0 0 20px ${C.coral}`,
          }}
        />
        {PHASES.map((_, i) => (
          <Node key={i} i={i} />
        ))}
      </div>

      <div style={{ position: "absolute", left: 150, right: 150, top: 470 }}>
        <PhaseCard />
      </div>
    </AbsoluteFill>
  );
};
