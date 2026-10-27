import {
  AbsoluteFill,
  Easing,
  interpolate,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { C, CLAMP, FONT_MONO } from "../theme";

export type Section = { readonly label: string; readonly from: number };

const EASE = Easing.bezier(0.215, 0.61, 0.355, 1); // power3.out
const MARGIN = 150; // matches the scenes' left/right content margin

// Persistent pitch-deck chrome: wordmark, section label + "03 / 08" counter,
// and a thin progress rail. The label swaps through a mask like a slide change.
export const DeckChrome: React.FC<{
  readonly sections: readonly Section[];
}> = ({ sections }) => {
  const frame = useCurrentFrame();
  const { durationInFrames } = useVideoConfig();

  let idx = 0;
  sections.forEach((s, i) => {
    if (frame >= s.from) idx = i;
  });
  const local = frame - sections[idx].from;
  const rise = interpolate(local, [0, 16], [100, 0], {
    ...CLAMP,
    easing: EASE,
  });
  const show = interpolate(
    frame,
    [8, 24, durationInFrames - 36, durationInFrames - 20],
    [0, 1, 1, 0],
    CLAMP,
  );
  const pad = (n: number) => String(n).padStart(2, "0");

  return (
    <AbsoluteFill style={{ opacity: show, pointerEvents: "none" }}>
      <div
        style={{
          position: "absolute",
          left: MARGIN,
          top: 44,
          fontFamily: FONT_MONO,
          fontSize: 22,
          letterSpacing: 6,
          color: C.dim,
        }}
      >
        <span style={{ color: C.coral }}>■</span> CYPHEX
      </div>

      <div
        style={{
          position: "absolute",
          right: MARGIN,
          top: 44,
          display: "flex",
          gap: 28,
          alignItems: "baseline",
          fontFamily: FONT_MONO,
          fontSize: 22,
          letterSpacing: 3,
          color: C.dim,
        }}
      >
        <span
          style={{ overflow: "hidden", height: 30, display: "inline-block" }}
        >
          <span
            style={{
              display: "inline-block",
              translate: `0px ${rise}%`,
              textTransform: "uppercase",
            }}
          >
            {sections[idx].label}
          </span>
        </span>
        <span style={{ color: C.text }}>
          {pad(idx + 1)}{" "}
          <span style={{ color: C.faint }}>/ {pad(sections.length)}</span>
        </span>
      </div>

      <div
        style={{
          position: "absolute",
          left: MARGIN,
          right: MARGIN,
          bottom: 44,
          height: 2,
          backgroundColor: C.line,
        }}
      >
        <div
          style={{
            width: `${(frame / durationInFrames) * 100}%`,
            height: "100%",
            backgroundColor: C.coral,
          }}
        />
      </div>
    </AbsoluteFill>
  );
};
