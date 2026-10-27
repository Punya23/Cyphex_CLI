import { Easing, interpolate, useCurrentFrame } from "remotion";
import { C, CLAMP } from "../theme";

const EASE_OUT = Easing.bezier(0.215, 0.61, 0.355, 1); // power3.out

export type Pt = { readonly x: number; readonly y: number };

// Horizontal-tangent cubic bezier, the same wire shape the command deck uses.
const controls = (a: Pt, b: Pt): [Pt, Pt] => {
  const k = Math.max(60, Math.abs(b.x - a.x) * 0.45);
  return [{ x: a.x + k, y: a.y }, { x: b.x - k, y: b.y }];
};

const pointAt = (a: Pt, b: Pt, t: number): Pt => {
  const [c1, c2] = controls(a, b);
  const u = 1 - t;
  return {
    x: u ** 3 * a.x + 3 * u * u * t * c1.x + 3 * u * t * t * c2.x + t ** 3 * b.x,
    y: u ** 3 * a.y + 3 * u * u * t * c1.y + 3 * u * t * t * c2.y + t ** 3 * b.y,
  };
};

// A wire that draws itself from `a` to `b` starting at `at`, with a pulse that
// rides the tip while drawing and then (if `loop`) keeps travelling the wire.
// Render inside a full-size <svg>.
export const FlowWire: React.FC<{
  readonly a: Pt;
  readonly b: Pt;
  readonly at: number;
  readonly len?: number;
  readonly color?: string;
  readonly loop?: boolean;
}> = ({ a, b, at, len = 20, color = C.coral, loop = false }) => {
  const frame = useCurrentFrame();
  const draw = interpolate(frame, [at, at + len], [0, 1], { ...CLAMP, easing: EASE_OUT });
  const [c1, c2] = controls(a, b);
  const t = draw < 1 ? draw : ((frame - at - len) * 0.025) % 1;
  const pt = pointAt(a, b, t);
  const showPulse = draw > 0 && (draw < 1 || loop);
  return (
    <g>
      <path
        d={`M ${a.x} ${a.y} C ${c1.x} ${c1.y}, ${c2.x} ${c2.y}, ${b.x} ${b.y}`}
        fill="none"
        stroke={draw > 0 ? color : C.line}
        strokeOpacity={0.85}
        strokeWidth={3}
        pathLength={1}
        strokeDasharray={1}
        strokeDashoffset={1 - draw}
      />
      {showPulse ? (
        <circle cx={pt.x} cy={pt.y} r={8} fill={color} style={{ filter: `drop-shadow(0 0 12px ${color})` }} />
      ) : null}
    </g>
  );
};
