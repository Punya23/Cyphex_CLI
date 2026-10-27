import {
  AbsoluteFill,
  Easing,
  Img,
  interpolate,
  staticFile,
  useCurrentFrame,
} from "remotion";
import { Appear, Cursor, TypeText } from "../components/kit";
import { C, CLAMP, FONT_DISPLAY, FONT_MONO } from "../theme";

const EASE_OUT = Easing.bezier(0.16, 1, 0.3, 1);

export const CTA: React.FC = () => {
  const frame = useCurrentFrame();
  const logo = interpolate(frame, [0, 20], [0, 1], {
    ...CLAMP,
    easing: EASE_OUT,
  });
  const line = interpolate(frame, [70, 88], [0, 1], {
    ...CLAMP,
    easing: EASE_OUT,
  });
  const fadeOut = interpolate(frame, [150, 180], [0, 1], CLAMP);

  return (
    <AbsoluteFill style={{ alignItems: "center" }}>
      <div
        style={{
          position: "absolute",
          top: 120,
          display: "flex",
          alignItems: "center",
          gap: 60,
          opacity: logo,
          translate: `0px ${(1 - logo) * 30}px`,
        }}
      >
        <Img
          src={staticFile("brand/mascot_hero.png")}
          style={{ width: 292, height: 323, imageRendering: "pixelated" }}
        />
        <Img
          src={staticFile("brand/banner_alpha.png")}
          style={{ width: 752, height: 215, imageRendering: "pixelated" }}
        />
      </div>

      <div
        style={{
          position: "absolute",
          top: 520,
          fontFamily: FONT_MONO,
          fontSize: 64,
          color: C.text,
          padding: "26px 48px",
          borderRadius: 18,
          border: `2px solid ${C.line}`,
          backgroundColor: C.panel,
        }}
      >
        <span style={{ color: C.coral }}>$ </span>
        <TypeText text="cx deep ./your-repo" from={24} charsPerFrame={0.6} />
        <Cursor size={56} />
      </div>

      <div
        style={{
          position: "absolute",
          top: 720,
          fontFamily: FONT_DISPLAY,
          fontWeight: 700,
          fontSize: 84,
          letterSpacing: -2,
          color: C.text,
          opacity: line,
          translate: `0px ${(1 - line) * 30}px`,
        }}
      >
        Point it at a repo.{" "}
        <span style={{ color: C.coral }}>It proves the rest.</span>
      </div>

      <Appear from={96} style={{ position: "absolute", top: 880 }}>
        <div style={{ fontFamily: FONT_MONO, fontSize: 34, color: C.dim }}>
          github.com/vedant91/Cyphex_CLI
        </div>
      </Appear>

      <AbsoluteFill style={{ backgroundColor: "#000", opacity: fadeOut }} />
    </AbsoluteFill>
  );
};
