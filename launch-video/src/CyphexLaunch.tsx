import { AbsoluteFill } from "remotion";
import { TransitionSeries, linearTiming } from "@remotion/transitions";
import { fade } from "@remotion/transitions/fade";
import { slide } from "@remotion/transitions/slide";
import { wipe } from "@remotion/transitions/wipe";
import { Backdrop } from "./components/Backdrop";
import { DeckChrome, type Section } from "./components/DeckChrome";
import { Voiceover } from "./components/Voiceover";
import { ColdOpen } from "./scenes/ColdOpen";
import { Commands } from "./scenes/Commands";
import { CTA } from "./scenes/CTA";
import { LocalFirst } from "./scenes/LocalFirst";
import { LogoReveal } from "./scenes/LogoReveal";
import { Pipeline } from "./scenes/Pipeline";
import { Problem } from "./scenes/Problem";
import { Swarm } from "./scenes/Swarm";
import { VerifyGate } from "./scenes/VerifyGate";

export const T = 12; // transition length, frames

// Scene lengths; Root derives total duration from these.
export const SCENES = [120, 150, 150, 270, 270, 270, 300, 150, 180] as const;
export const TOTAL_FRAMES =
  SCENES.reduce((a, b) => a + b, 0) - T * (SCENES.length - 1);

const timing = linearTiming({ durationInFrames: T });

const LABELS = [
  "Intro",
  "Problem",
  "Product",
  "Commands",
  "Pipeline",
  "Swarm",
  "Verify",
  "Local-first",
  "Get started",
];
// Each scene starts where the previous one ends minus the transition overlap.
const SECTIONS: Section[] = LABELS.map((label, i) => ({
  label,
  from: SCENES.slice(0, i).reduce((a, b) => a + b, 0) - T * i,
}));

export const CyphexLaunch: React.FC = () => {
  return (
    <AbsoluteFill>
      <Backdrop />
      <TransitionSeries>
        <TransitionSeries.Sequence
          name="Cold open"
          durationInFrames={SCENES[0]}
        >
          <ColdOpen />
        </TransitionSeries.Sequence>
        <TransitionSeries.Transition presentation={fade()} timing={timing} />
        <TransitionSeries.Sequence name="Problem" durationInFrames={SCENES[1]}>
          <Problem />
        </TransitionSeries.Sequence>
        <TransitionSeries.Transition presentation={fade()} timing={timing} />
        <TransitionSeries.Sequence
          name="Logo reveal"
          durationInFrames={SCENES[2]}
        >
          <LogoReveal />
        </TransitionSeries.Sequence>
        <TransitionSeries.Transition presentation={fade()} timing={timing} />
        <TransitionSeries.Sequence name="Commands" durationInFrames={SCENES[3]}>
          <Commands />
        </TransitionSeries.Sequence>
        <TransitionSeries.Transition
          presentation={slide({ direction: "from-right" })}
          timing={timing}
        />
        <TransitionSeries.Sequence name="Pipeline" durationInFrames={SCENES[4]}>
          <Pipeline />
        </TransitionSeries.Sequence>
        <TransitionSeries.Transition
          presentation={wipe({ direction: "from-left" })}
          timing={timing}
        />
        <TransitionSeries.Sequence name="Swarm" durationInFrames={SCENES[5]}>
          <Swarm />
        </TransitionSeries.Sequence>
        <TransitionSeries.Transition
          presentation={slide({ direction: "from-bottom" })}
          timing={timing}
        />
        <TransitionSeries.Sequence
          name="Verify gate"
          durationInFrames={SCENES[6]}
        >
          <VerifyGate />
        </TransitionSeries.Sequence>
        <TransitionSeries.Transition presentation={fade()} timing={timing} />
        <TransitionSeries.Sequence
          name="Local first"
          durationInFrames={SCENES[7]}
        >
          <LocalFirst />
        </TransitionSeries.Sequence>
        <TransitionSeries.Transition presentation={fade()} timing={timing} />
        <TransitionSeries.Sequence name="CTA" durationInFrames={SCENES[8]}>
          <CTA />
        </TransitionSeries.Sequence>
      </TransitionSeries>
      <DeckChrome sections={SECTIONS} />
      <Voiceover sections={SECTIONS} />
    </AbsoluteFill>
  );
};
