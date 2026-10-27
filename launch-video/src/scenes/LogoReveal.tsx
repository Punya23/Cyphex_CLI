import {
  AbsoluteFill,
  Easing,
  Img,
  interpolate,
  staticFile,
  useCurrentFrame,
} from "remotion";
import { Appear } from "../components/kit";
import { C, CLAMP, FONT_DISPLAY, FONT_MONO } from "../theme";

const EASE_OUT = Easing.bezier(0.16, 1, 0.3, 1);
const EASE_POP = Easing.bezier(0.34, 1.56, 0.64, 1);

const TagWord: React.FC<{
  readonly children: string;
  readonly at: number;
  readonly color: string;
}> = ({ children, at, color }) => {
  const frame = useCurrentFrame();
  const p = interpolate(frame, [at, at + 16], [0, 1], {
    ...CLAMP,
    easing: EASE_OUT,
  });
  return (
    <span
      style={{
        display: "inline-block",
        opacity: p,
        translate: `0px ${(1 - p) * 40}px`,
        color,
        marginRight: 40,
      }}
    >
      {children}
    </span>
  );
};

export const LogoReveal: React.FC = () => {
  const frame = useCurrentFrame();

  // Banner wipes in left→right, then briefly chromatic-glitches on landing.
  const wipe = interpolate(frame, [6, 34], [100, 0], {
    ...CLAMP,
    easing: EASE_OUT,
  });
  const glitch = interpolate(frame, [34, 38, 48], [0, 1, 0], CLAMP);
  const mascotP = interpolate(frame, [14, 38], [0, 1], {
    ...CLAMP,
    easing: EASE_POP,
  });
  const bob = Math.sin(frame / 9) * 8;
  const glow = interpolate(frame, [30, 60], [0, 1], CLAMP);

  return (
    <AbsoluteFill style={{ alignItems: "center", justifyContent: "center" }}>
      <div
        style={{
          position: "absolute",
          top: 200,
          display: "flex",
          alignItems: "center",
          gap: 90,
        }}
      >
        <div
          style={{
            opacity: mascotP,
            scale: 0.6 + mascotP * 0.4,
            translate: `0px ${bob}px`,
            filter: `drop-shadow(0 0 ${60 * glow}px ${C.coral}88)`,
          }}
        >
          <Img
            src={staticFile("brand/mascot_hero.png")}
            style={{
              width: 292 * 1.3,
              height: 323 * 1.3,
              imageRendering: "pixelated",
            }}
          />
        </div>
        <div
          style={{
            clipPath: `inset(0 ${wipe}% 0 0)`,
            filter: `drop-shadow(${12 * glitch}px 0 0 #22d3ee88) drop-shadow(${-12 * glitch}px 0 0 #f4258f88) drop-shadow(0 0 ${40 * glow}px ${C.coral}55)`,
          }}
        >
          <Img
            src={staticFile("brand/banner_alpha.png")}
            style={{
              width: 752 * 1.5,
              height: 215 * 1.5,
              imageRendering: "pixelated",
            }}
          />
        </div>
      </div>

      <div
        style={{
          position: "absolute",
          top: 700,
          left: 0,
          right: 0,
          textAlign: "center",
        }}
      >
        <div
          style={{
            fontFamily: FONT_DISPLAY,
            fontWeight: 700,
            fontSize: 112,
            letterSpacing: -2,
          }}
        >
          <TagWord at={44} color={C.text}>
            Attack.
          </TagWord>
          <TagWord at={54} color={C.text}>
            Patch.
          </TagWord>
          <TagWord at={64} color={C.coral}>
            Prove.
          </TagWord>
        </div>
        <Appear from={82} style={{ marginTop: 28 }}>
          <div
            style={{
              fontFamily: FONT_MONO,
              fontSize: 36,
              color: C.dim,
              letterSpacing: 1,
            }}
          >
            The AI security agent that proves its fixes.
          </div>
        </Appear>
      </div>
    </AbsoluteFill>
  );
};
