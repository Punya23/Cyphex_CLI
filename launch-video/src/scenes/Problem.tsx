import { AbsoluteFill, Easing, interpolate, useCurrentFrame } from "remotion";
import { Appear, Eyebrow, Headline, Pill } from "../components/kit";
import { C, CLAMP, FONT_DISPLAY } from "../theme";

const EASE_OUT = Easing.bezier(0.16, 1, 0.3, 1);

const Word: React.FC<{
  readonly children: string;
  readonly at: number;
  readonly strike?: boolean;
}> = ({ children, at, strike }) => {
  const frame = useCurrentFrame();
  const p = interpolate(frame, [at, at + 14], [0, 1], { ...CLAMP, easing: EASE_OUT });
  const bar = interpolate(frame, [68, 80], [0, 1], { ...CLAMP, easing: EASE_OUT });
  return (
    <span
      style={{
        position: "relative",
        display: "inline-block",
        opacity: p,
        translate: `0px ${(1 - p) * 34}px`,
        marginRight: 28,
      }}
    >
      {children}
      {strike ? (
        <span
          style={{
            position: "absolute",
            left: -6,
            right: -6,
            top: "54%",
            height: 10,
            backgroundColor: C.red,
            borderRadius: 5,
            transformOrigin: "left center",
            scale: `${bar} 1`,
            boxShadow: `0 0 28px ${C.red}`,
          }}
        />
      ) : null}
    </span>
  );
};

const Claim: React.FC<{ readonly at: number }> = ({ at }) => {
  const frame = useCurrentFrame();
  const p = interpolate(frame, [at, at + 12], [0, 1], { ...CLAMP, easing: EASE_OUT });
  // At frame 80 the confident green "FIXED" claims lose their proof.
  const turn = interpolate(frame, [80, 90], [0, 1], CLAMP);
  const color = turn > 0.5 ? C.amber : C.green;
  const label = turn > 0.5 ? "? UNPROVEN" : "✓ FIXED";
  return (
    <div style={{ opacity: p, scale: 0.8 + p * 0.2 }}>
      <Pill label={label} color={color} size={30} />
    </div>
  );
};

export const Problem: React.FC = () => {
  const frame = useCurrentFrame();

  const dim = interpolate(frame, [96, 112], [1, 0.16], { ...CLAMP, easing: EASE_OUT });
  const punch = interpolate(frame, [98, 116], [0, 1], { ...CLAMP, easing: EASE_OUT });

  return (
    <AbsoluteFill style={{ paddingLeft: 150, paddingTop: 130 }}>
      <Appear from={0}>
        <Eyebrow>The problem</Eyebrow>
      </Appear>

      <div style={{ opacity: dim, marginTop: 48 }}>
        <Headline size={112}>
          <div>
            <Word at={6}>Every</Word>
            <Word at={10}>AI</Word>
            <Word at={14}>security</Word>
            <Word at={18}>tool</Word>
          </div>
          <div>
            <Word at={24}>says</Word>
            <Word at={28}>it</Word>
            <Word at={32} strike>
              fixed
            </Word>
            <Word at={36}>your</Word>
            <Word at={40}>code.</Word>
          </div>
        </Headline>

        <div style={{ display: "flex", gap: 28, marginTop: 56 }}>
          {[48, 54, 60, 66].map((at) => (
            <Claim key={at} at={at} />
          ))}
        </div>
      </div>

      <div
        style={{
          position: "absolute",
          left: 150,
          right: 150,
          top: 640,
          fontFamily: FONT_DISPLAY,
          fontWeight: 700,
          fontSize: 128,
          lineHeight: 1.02,
          letterSpacing: -4,
          color: C.coral,
          opacity: punch,
          translate: `0px ${(1 - punch) * 60}px`,
          textShadow: `0 0 80px ${C.coral}66`,
        }}
      >
        None of them can <span style={{ color: C.text }}>show you.</span>
      </div>
    </AbsoluteFill>
  );
};
