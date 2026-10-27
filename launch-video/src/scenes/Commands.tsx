import { AbsoluteFill, Easing, Img, interpolate, staticFile, useCurrentFrame } from "remotion";
import { Appear, Cursor, Eyebrow, Headline } from "../components/kit";
import { C, CLAMP, FONT_MONO } from "../theme";

const EASE_OUT = Easing.bezier(0.215, 0.61, 0.355, 1); // power3.out
const CYAN = "#22d3ee"; // slash-command colour in the real CLI

// Real commands + descriptions from the CLI's /help command deck.
const COMMANDS = [
  { cmd: "/scan <path|url>", desc: "Acquire & scan a target" },
  { cmd: "/deep <path>", desc: "DeepAgents attack swarm" },
  { cmd: "/full <path>", desc: "DeepAgents + network sweep" },
  { cmd: "/net [host]", desc: "Network map / host audit" },
  { cmd: "/watch", desc: "Arm the RASP auto-healing daemon" },
  { cmd: "/doctor", desc: "Models, tools & dependencies" },
  { cmd: "/verify <scan_id>", desc: "Replay a run: score + verdicts" },
];

const P0 = { x: 590, y: 560 };
const ROW_X = 790;
const ROW_Y0 = 290;
const ROW_GAP = 100;
const WIRE_START = 30;
const WIRE_STEP = 12;
const WIRE_LEN = 20;
const ACTIVE_FROM = 150;
const ACTIVE_EVERY = 22;

const rowY = (i: number): number => ROW_Y0 + i * ROW_GAP;

// Cubic bezier from the prompt node to a command row's left edge.
const wirePath = (i: number): string => {
  const y = rowY(i);
  return `M ${P0.x} ${P0.y} C ${P0.x + 110} ${P0.y}, ${ROW_X - 110} ${y}, ${ROW_X} ${y}`;
};

const bezierPoint = (i: number, t: number): { x: number; y: number } => {
  const y = rowY(i);
  const [x0, y0, x1, y1, x2, y2, x3, y3] = [P0.x, P0.y, P0.x + 110, P0.y, ROW_X - 110, y, ROW_X, y];
  const u = 1 - t;
  return {
    x: u * u * u * x0 + 3 * u * u * t * x1 + 3 * u * t * t * x2 + t * t * t * x3,
    y: u * u * u * y0 + 3 * u * u * t * y1 + 3 * u * t * t * y2 + t * t * t * y3,
  };
};

const Wire: React.FC<{ readonly i: number; readonly active: boolean }> = ({ i, active }) => {
  const frame = useCurrentFrame();
  const at = WIRE_START + i * WIRE_STEP;
  const draw = interpolate(frame, [at, at + WIRE_LEN], [0, 1], { ...CLAMP, easing: EASE_OUT });
  const pulseT = draw < 1 ? draw : ((frame - at - WIRE_LEN) * 0.025) % 1;
  const showPulse = draw > 0 && (draw < 1 || active);
  const pt = bezierPoint(i, pulseT);
  const color = active ? C.coral : C.line;
  return (
    <g>
      <path
        d={wirePath(i)}
        fill="none"
        stroke={color}
        strokeWidth={3}
        pathLength={1}
        strokeDasharray={1}
        strokeDashoffset={1 - draw}
      />
      {showPulse ? <circle cx={pt.x} cy={pt.y} r={8} fill={C.coral} style={{ filter: `drop-shadow(0 0 12px ${C.coral})` }} /> : null}
    </g>
  );
};

const Row: React.FC<{ readonly i: number; readonly active: boolean }> = ({ i, active }) => {
  const frame = useCurrentFrame();
  const at = WIRE_START + i * WIRE_STEP + WIRE_LEN - 4;
  const p = interpolate(frame, [at, at + 14], [0, 1], { ...CLAMP, easing: EASE_OUT });
  const { cmd, desc } = COMMANDS[i];
  return (
    <div
      style={{
        position: "absolute",
        left: ROW_X,
        top: rowY(i) - 38,
        height: 76,
        display: "flex",
        alignItems: "center",
        gap: 40,
        opacity: p,
        translate: `${(1 - p) * 40}px 0px`,
      }}
    >
      <div
        style={{
          width: 380,
          padding: "0 26px",
          height: 76,
          display: "flex",
          alignItems: "center",
          borderRadius: 14,
          border: `2px solid ${active ? C.coral : C.line}`,
          backgroundColor: C.panel,
          boxShadow: active ? `0 0 40px ${C.coral}55` : "none",
          fontFamily: FONT_MONO,
          fontSize: 30,
          color: CYAN,
        }}
      >
        {cmd}
      </div>
      <div style={{ fontFamily: FONT_MONO, fontSize: 28, color: active ? C.text : C.dim, width: 560 }}>{desc}</div>
    </div>
  );
};

export const Commands: React.FC = () => {
  const frame = useCurrentFrame();
  const nodeIn = interpolate(frame, [6, 24], [0, 1], { ...CLAMP, easing: EASE_OUT });
  const hacking = frame >= WIRE_START;
  const bob = Math.sin(frame / 9) * 6;
  const active = frame >= ACTIVE_FROM ? Math.floor((frame - ACTIVE_FROM) / ACTIVE_EVERY) % COMMANDS.length : -1;

  return (
    <AbsoluteFill>
      <div style={{ position: "absolute", left: 150, top: 96 }}>
        <Appear from={0}>
          <Eyebrow>The command deck</Eyebrow>
        </Appear>
        <Appear from={6} style={{ marginTop: 18 }}>
          <Headline size={78}>One prompt. Every capability.</Headline>
        </Appear>
      </div>

      <svg width={1920} height={1080} style={{ position: "absolute", inset: 0 }}>
        {COMMANDS.map((_, i) => (
          <Wire key={i} i={i} active={i === active} />
        ))}
      </svg>

      {COMMANDS.map((_, i) => (
        <Row key={i} i={i} active={i === active} />
      ))}

      {/* buddy + prompt node */}
      <div
        style={{
          position: "absolute",
          left: 150,
          top: P0.y - 190,
          width: 440,
          opacity: nodeIn,
          translate: `0px ${(1 - nodeIn) * 30}px`,
        }}
      >
        <div style={{ display: "flex", justifyContent: "center", translate: `0px ${bob}px` }}>
          <Img
            src={staticFile(hacking ? "brand/expr_hacking.png" : "brand/expr_focused.png")}
            style={{ width: 190, height: 190, objectFit: "contain", imageRendering: "pixelated" }}
          />
        </div>
        <div
          style={{
            marginTop: 14,
            height: 90,
            display: "flex",
            alignItems: "center",
            padding: "0 26px",
            borderRadius: 16,
            border: `2px solid ${C.coral}`,
            backgroundColor: C.panel,
            boxShadow: `0 0 50px ${C.coral}44`,
            fontFamily: FONT_MONO,
            fontSize: 34,
            color: C.text,
          }}
        >
          <span style={{ color: C.coral }}>cx ▸&nbsp;</span>
          <span style={{ color: CYAN }}>/</span>
          <Cursor size={32} />
        </div>
      </div>
    </AbsoluteFill>
  );
};
