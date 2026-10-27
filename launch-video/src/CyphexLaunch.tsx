import { AbsoluteFill } from "remotion";
import { TransitionSeries, linearTiming } from "@remotion/transitions";
import { fade } from "@remotion/transitions/fade";
import { slide } from "@remotion/transitions/slide";
import { wipe } from "@remotion/transitions/wipe";
import { Backdrop } from "./components/Backdrop";
import { ColdOpen } from "./scenes/ColdOpen";
import { CTA } from "./scenes/CTA";
import { LocalFirst } from "./scenes/LocalFirst";
import { LogoReveal } from "./scenes/LogoReveal";
import { Pipeline } from "./scenes/Pipeline";
import { Problem } from "./scenes/Problem";
import { Swarm } from "./scenes/Swarm";
import { VerifyGate } from "./scenes/VerifyGate";

export const T = 12; // transition length, frames

// Scene lengths; Root derives total duration from these.
export const SCENES = [120, 150, 150, 270, 270, 300, 150, 180] as const;
export const TOTAL_FRAMES = SCENES.reduce((a, b) => a + b, 0) - T * (SCENES.length - 1);

const timing = linearTiming({ durationInFrames: T });

export const CyphexLaunch: React.FC = () => {
  return (
    <AbsoluteFill>
      <Backdrop />
      <TransitionSeries>
        <TransitionSeries.Sequence name="Cold open" durationInFrames={SCENES[0]}>
          <ColdOpen />
        </TransitionSeries.Sequence>
        <TransitionSeries.Transition presentation={fade()} timing={timing} />
        <TransitionSeries.Sequence name="Problem" durationInFrames={SCENES[1]}>
          <Problem />
        </TransitionSeries.Sequence>
        <TransitionSeries.Transition presentation={fade()} timing={timing} />
        <TransitionSeries.Sequence name="Logo reveal" durationInFrames={SCENES[2]}>
          <LogoReveal />
        </TransitionSeries.Sequence>
        <TransitionSeries.Transition presentation={slide({ direction: "from-right" })} timing={timing} />
        <TransitionSeries.Sequence name="Pipeline" durationInFrames={SCENES[3]}>
          <Pipeline />
        </TransitionSeries.Sequence>
        <TransitionSeries.Transition presentation={wipe({ direction: "from-left" })} timing={timing} />
        <TransitionSeries.Sequence name="Swarm" durationInFrames={SCENES[4]}>
          <Swarm />
        </TransitionSeries.Sequence>
        <TransitionSeries.Transition presentation={slide({ direction: "from-bottom" })} timing={timing} />
        <TransitionSeries.Sequence name="Verify gate" durationInFrames={SCENES[5]}>
          <VerifyGate />
        </TransitionSeries.Sequence>
        <TransitionSeries.Transition presentation={fade()} timing={timing} />
        <TransitionSeries.Sequence name="Local first" durationInFrames={SCENES[6]}>
          <LocalFirst />
        </TransitionSeries.Sequence>
        <TransitionSeries.Transition presentation={fade()} timing={timing} />
        <TransitionSeries.Sequence name="CTA" durationInFrames={SCENES[7]}>
          <CTA />
        </TransitionSeries.Sequence>
      </TransitionSeries>
    </AbsoluteFill>
  );
};
