import React from "react";
import { Easing, interpolate, useCurrentFrame } from "remotion";
import { C, CLAMP, FONT_DISPLAY, FONT_MONO } from "../theme";

const EASE_OUT = Easing.bezier(0.16, 1, 0.3, 1);

// Fade + rise into place, driven purely by the frame.
export const Appear: React.FC<{
  readonly from: number;
  readonly duration?: number;
  readonly rise?: number;
  readonly style?: React.CSSProperties;
  readonly children: React.ReactNode;
}> = ({ from, duration = 18, rise = 28, style, children }) => {
  const frame = useCurrentFrame();
  const p = interpolate(frame, [from, from + duration], [0, 1], {
    ...CLAMP,
    easing: EASE_OUT,
  });
  return (
    <div
      style={{
        opacity: p,
        translate: `0px ${(1 - p) * rise}px`,
        ...style,
      }}
    >
      {children}
    </div>
  );
};

export const Cursor: React.FC<{ readonly color?: string; readonly size?: number }> = ({
  color = C.coral,
  size = 40,
}) => {
  const frame = useCurrentFrame();
  const on = Math.floor(frame / 15) % 2 === 0;
  return (
    <span
      style={{
        display: "inline-block",
        width: size * 0.55,
        height: size * 1.05,
        marginLeft: 6,
        backgroundColor: color,
        opacity: on ? 1 : 0,
        verticalAlign: "text-bottom",
      }}
    />
  );
};

// Character-by-character typing. `charsPerFrame` < 1 slows it down.
export const TypeText: React.FC<{
  readonly text: string;
  readonly from: number;
  readonly charsPerFrame?: number;
}> = ({ text, from, charsPerFrame = 0.6 }) => {
  const frame = useCurrentFrame();
  const n = Math.max(0, Math.min(text.length, Math.floor((frame - from) * charsPerFrame)));
  return <>{text.slice(0, n)}</>;
};

export const Pill: React.FC<{
  readonly label: string;
  readonly color: string;
  readonly size?: number;
  readonly filled?: boolean;
  readonly style?: React.CSSProperties;
}> = ({ label, color, size = 28, filled = false, style }) => (
  <div
    style={{
      fontFamily: FONT_MONO,
      fontWeight: 700,
      fontSize: size,
      letterSpacing: 1.5,
      color: filled ? C.bg : color,
      backgroundColor: filled ? color : `${color}18`,
      border: `2px solid ${color}`,
      borderRadius: size * 0.4,
      padding: `${size * 0.28}px ${size * 0.7}px`,
      display: "inline-flex",
      alignItems: "center",
      gap: size * 0.4,
      boxShadow: `0 0 ${size}px ${color}33`,
      ...style,
    }}
  >
    {label}
  </div>
);

export const Eyebrow: React.FC<{ readonly children: React.ReactNode; readonly color?: string }> = ({
  children,
  color = C.coral,
}) => (
  <div
    style={{
      fontFamily: FONT_MONO,
      fontWeight: 700,
      fontSize: 30,
      letterSpacing: 8,
      color,
      textTransform: "uppercase",
    }}
  >
    {children}
  </div>
);

export const Headline: React.FC<{
  readonly children: React.ReactNode;
  readonly size?: number;
  readonly style?: React.CSSProperties;
}> = ({ children, size = 104, style }) => (
  <div
    style={{
      fontFamily: FONT_DISPLAY,
      fontWeight: 700,
      fontSize: size,
      lineHeight: 1.04,
      letterSpacing: -2,
      color: C.text,
      ...style,
    }}
  >
    {children}
  </div>
);

// Terminal window chrome used by several scenes.
export const TerminalWindow: React.FC<{
  readonly title: string;
  readonly width: number;
  readonly height?: number;
  readonly children: React.ReactNode;
  readonly style?: React.CSSProperties;
}> = ({ title, width, height, children, style }) => (
  <div
    style={{
      width,
      height,
      backgroundColor: C.panel,
      border: `2px solid ${C.line}`,
      borderRadius: 22,
      overflow: "hidden",
      boxShadow: `0 40px 120px #000c, 0 0 80px ${C.coral}14`,
      ...style,
    }}
  >
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: 12,
        padding: "18px 24px",
        backgroundColor: C.panelHi,
        borderBottom: `2px solid ${C.line}`,
      }}
    >
      <div style={{ width: 16, height: 16, borderRadius: 8, backgroundColor: C.red }} />
      <div style={{ width: 16, height: 16, borderRadius: 8, backgroundColor: C.amber }} />
      <div style={{ width: 16, height: 16, borderRadius: 8, backgroundColor: C.green }} />
      <div
        style={{
          marginLeft: 16,
          fontFamily: FONT_MONO,
          fontSize: 22,
          color: C.dim,
          letterSpacing: 1,
        }}
      >
        {title}
      </div>
    </div>
    <div style={{ padding: 36 }}>{children}</div>
  </div>
);
