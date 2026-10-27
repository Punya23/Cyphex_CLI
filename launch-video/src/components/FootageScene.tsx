import { AbsoluteFill, Easing, OffthreadVideo, interpolate, staticFile, useCurrentFrame } from "remotion";
import { Appear, Eyebrow, Headline } from "./kit";
import { C, CLAMP, FONT_MONO } from "../theme";

const EASE_OUT = Easing.bezier(0.215, 0.61, 0.355, 1); // power3.out
const EASE_IO = Easing.bezier(0.645, 0.045, 0.355, 1); // power3.inOut
const CYAN = "#22d3ee";

// The real terminal window. Aspect matches the 3456x2234 recording, so nothing is cropped.
const WIN = { x: 40, y: 82, w: 1470, h: 950 } as const;
const COL = { x: 1542, w: 338 } as const;

/** Camera keyframe: centre (cx, cy in 0..1 of the recording) and zoom, from frame `f`. */
export type ZoomKey = { readonly f: number; readonly cx: number; readonly cy: number; readonly z: number };
/** Right-column callout that appears at frame `at`. */
export type Card = {
  readonly at: number;
  readonly title: string;
  readonly sub?: string;
  readonly chips?: readonly string[];
  readonly color?: string;
};
/** Highlight box in recording coordinates (0..1), visible from `from` to `to`. */
export type Mark = {
  readonly from: number;
  readonly to: number;
  readonly x: number;
  readonly y: number;
  readonly w: number;
  readonly h: number;
};

const camera = (keys: readonly ZoomKey[], frame: number): Pick<ZoomKey, "cx" | "cy" | "z"> => {
  if (keys.length === 0) return { cx: 0.5, cy: 0.5, z: 1 };
  if (frame <= keys[0].f) return keys[0];
  for (let i = 0; i < keys.length - 1; i++) {
    const a = keys[i];
    const b = keys[i + 1];
    if (frame < b.f) {
      const t = EASE_IO((frame - a.f) / (b.f - a.f));
      return { cx: a.cx + (b.cx - a.cx) * t, cy: a.cy + (b.cy - a.cy) * t, z: a.z + (b.z - a.z) * t };
    }
  }
  return keys[keys.length - 1];
};

const clamp = (v: number, lo: number, hi: number): number => Math.min(hi, Math.max(lo, v));

export const FootageScene: React.FC<{
  readonly clip: string;
  readonly eyebrow: string;
  readonly headline: string;
  /** Shown in the window badge, e.g. "2× speed". */
  readonly note?: string;
  readonly cards: readonly Card[];
  readonly zoom?: readonly ZoomKey[];
  readonly marks?: readonly Mark[];
}> = ({ clip, eyebrow, headline, note, cards, zoom = [], marks = [] }) => {
  const frame = useCurrentFrame();
  const { cx, cy, z } = camera(zoom, frame);
  const tx = clamp(WIN.w / 2 - z * cx * WIN.w, WIN.w * (1 - z), 0);
  const ty = clamp(WIN.h / 2 - z * cy * WIN.h, WIN.h * (1 - z), 0);
  const winIn = interpolate(frame, [0, 14], [0, 1], { ...CLAMP, easing: EASE_OUT });
  const shown = cards.filter((c) => frame >= c.at);
  const activeAt = shown.length ? shown[shown.length - 1].at : -1;
  const compact = cards.length > 4;

  return (
    <AbsoluteFill>
      <div
        style={{
          position: "absolute",
          left: WIN.x,
          top: WIN.y,
          width: WIN.w,
          height: WIN.h,
          borderRadius: 14,
          overflow: "hidden",
          border: `2px solid ${C.line}`,
          backgroundColor: "#000",
          boxShadow: `0 30px 100px #000c, 0 0 80px ${C.coral}22`,
          opacity: winIn,
          scale: 0.97 + winIn * 0.03,
        }}
      >
        <div
          style={{
            width: WIN.w,
            height: WIN.h,
            transformOrigin: "0 0",
            transform: `translate(${tx}px, ${ty}px) scale(${z})`,
          }}
        >
          <OffthreadVideo src={staticFile(`footage/${clip}.mp4`)} muted style={{ width: WIN.w, height: WIN.h }} />
        </div>

        {marks.map((m) => {
          const p = interpolate(frame, [m.from, m.from + 8, m.to - 8, m.to], [0, 1, 1, 0], CLAMP);
          return (
            <div
              key={`${m.from}-${m.x}-${m.y}`}
              style={{
                position: "absolute",
                left: tx + z * m.x * WIN.w,
                top: ty + z * m.y * WIN.h,
                width: z * m.w * WIN.w,
                height: z * m.h * WIN.h,
                border: `3px solid ${C.coral}`,
                borderRadius: 8,
                boxShadow: `0 0 30px ${C.coral}88`,
                opacity: p,
              }}
            />
          );
        })}

        <div
          style={{
            position: "absolute",
            right: 14,
            top: 12,
            padding: "6px 14px",
            borderRadius: 20,
            backgroundColor: "#000c",
            border: `1px solid ${C.line}`,
            fontFamily: FONT_MONO,
            fontSize: 16,
            letterSpacing: 2,
            color: C.dim,
          }}
        >
          <span style={{ color: C.coral }}>●</span> REAL TERMINAL{note ? ` · ${note}` : ""}
        </div>
      </div>

      <div style={{ position: "absolute", left: COL.x, top: 96, width: COL.w }}>
        <Appear from={0}>
          <Eyebrow>{eyebrow}</Eyebrow>
        </Appear>
        <Appear from={6} style={{ marginTop: 14 }}>
          <Headline size={40}>{headline}</Headline>
        </Appear>
      </div>

      <div style={{ position: "absolute", left: COL.x, top: 340, width: COL.w, display: "flex", flexDirection: "column", gap: compact ? 9 : 14 }}>
        {shown.map((c) => {
          const p = interpolate(frame, [c.at, c.at + 12], [0, 1], { ...CLAMP, easing: EASE_OUT });
          const active = c.at === activeAt;
          const color = c.color ?? C.coral;
          return (
            <div
              key={c.at}
              style={{
                padding: compact ? "9px 16px" : "14px 18px",
                borderRadius: 14,
                borderLeft: `5px solid ${active ? color : C.line}`,
                border: `2px solid ${active ? color : C.line}`,
                borderLeftWidth: 5,
                backgroundColor: C.panel,
                boxShadow: active ? `0 0 34px ${color}44` : "none",
                opacity: (active ? 1 : 0.62) * p,
                translate: `${(1 - p) * 30}px 0px`,
                fontFamily: FONT_MONO,
              }}
            >
              <div style={{ fontSize: compact ? 21 : 24, fontWeight: 700, color: active ? color : C.text, lineHeight: 1.2 }}>{c.title}</div>
              {c.sub ? <div style={{ fontSize: compact ? 16 : 19, color: C.dim, marginTop: compact ? 3 : 6, lineHeight: 1.3 }}>{c.sub}</div> : null}
              {c.chips ? (
                <div style={{ display: "flex", flexWrap: "wrap", gap: 8, marginTop: compact ? 5 : 8 }}>
                  {c.chips.map((chip) => (
                    <span key={chip} style={{ fontSize: 16, color: CYAN, border: `1px solid ${CYAN}66`, borderRadius: 8, padding: "2px 8px" }}>
                      {chip}
                    </span>
                  ))}
                </div>
              ) : null}
            </div>
          );
        })}
      </div>
    </AbsoluteFill>
  );
};
