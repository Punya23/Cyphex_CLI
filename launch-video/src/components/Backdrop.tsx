import {
  AbsoluteFill,
  interpolate,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { C } from "../theme";

// Persistent cinematic background: dark base, slow-drifting coral/violet
// glows, a faint perspective-free grid, then film grain + scanlines + vignette
// stacked on top. Everything is frame-driven (no CSS animation).
export const Backdrop: React.FC = () => {
  const frame = useCurrentFrame();
  const { width, height, durationInFrames } = useVideoConfig();

  const drift = interpolate(frame, [0, durationInFrames], [0, 1]);

  return (
    <AbsoluteFill style={{ backgroundColor: C.bg }}>
      <AbsoluteFill
        style={{
          background: `radial-gradient(900px 700px at ${20 + drift * 30}% ${30 + Math.sin(drift * 6.28) * 12}%, ${C.coral}22, transparent 70%), radial-gradient(1000px 800px at ${85 - drift * 25}% ${75 - Math.cos(drift * 6.28) * 10}%, ${C.purple}26, transparent 70%)`,
        }}
      />
      <AbsoluteFill
        style={{
          // midnight-grid dot grid: 2px dots on a 40px pitch, slow lagging drift
          backgroundImage: `radial-gradient(circle, ${C.faint} 2px, transparent 2.5px)`,
          backgroundSize: "40px 40px",
          backgroundPosition: `${(frame * 0.2) % 40}px ${(frame * 0.12) % 40}px`,
          maskImage:
            "radial-gradient(ellipse at 50% 50%, black 10%, transparent 75%)",
          WebkitMaskImage:
            "radial-gradient(ellipse at 50% 50%, black 10%, transparent 75%)",
          opacity: 0.55,
        }}
      />
      {/* film grain: reseeded every other frame so it shimmers, not crawls */}
      <svg
        width={width}
        height={height}
        style={{
          position: "absolute",
          inset: 0,
          opacity: 0.07,
          mixBlendMode: "screen",
        }}
      >
        <filter id="grain">
          <feTurbulence
            type="fractalNoise"
            baseFrequency="0.9"
            numOctaves="2"
            seed={Math.floor(frame / 2) % 50}
          />
          <feColorMatrix type="saturate" values="0" />
        </filter>
        <rect width="100%" height="100%" filter="url(#grain)" />
      </svg>
      <AbsoluteFill
        style={{
          background:
            "radial-gradient(ellipse at 50% 50%, transparent 45%, rgba(0,0,0,0.75) 100%)",
        }}
      />
    </AbsoluteFill>
  );
};
