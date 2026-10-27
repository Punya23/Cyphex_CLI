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
import { Compare } from "./scenes/Compare";
import { CTA } from "./scenes/CTA";
import { Debate } from "./scenes/Debate";
import { DecisionGate } from "./scenes/DecisionGate";
import { Genome } from "./scenes/Genome";
import { Hypothesis } from "./scenes/Hypothesis";
import { LocalFirst } from "./scenes/LocalFirst";
import { LogoReveal } from "./scenes/LogoReveal";
import { Pipeline } from "./scenes/Pipeline";
import { Problem } from "./scenes/Problem";
import { Swarm } from "./scenes/Swarm";
import { VerifyGate } from "./scenes/VerifyGate";

export const T = 12; // transition length, frames

const timing = linearTiming({ durationInFrames: T });

// Transition INTO a scene, by name (the presentation types don't unify).
const ENTER = {
  fade: (key: string) => <TransitionSeries.Transition key={key} presentation={fade()} timing={timing} />,
  slideRight: (key: string) => (
    <TransitionSeries.Transition key={key} presentation={slide({ direction: "from-right" })} timing={timing} />
  ),
  slideBottom: (key: string) => (
    <TransitionSeries.Transition key={key} presentation={slide({ direction: "from-bottom" })} timing={timing} />
  ),
  wipeLeft: (key: string) => (
    <TransitionSeries.Transition key={key} presentation={wipe({ direction: "from-left" })} timing={timing} />
  ),
} as const;

// One row per scene, in playback order. `enter` is the transition INTO the scene.
// Voiceover anchors in components/Voiceover.tsx refer to a scene by its `id`.
const DECK: readonly {
  readonly id: string;
  readonly label: string;
  readonly frames: number;
  readonly Comp: React.FC;
  readonly enter?: keyof typeof ENTER;
}[] = [
  { id: "intro", label: "Intro", frames: 120, Comp: ColdOpen },
  { id: "problem", label: "Problem", frames: 150, Comp: Problem, enter: "fade" },
  { id: "logo", label: "Product", frames: 150, Comp: LogoReveal, enter: "fade" },
  { id: "commands", label: "Commands", frames: 270, Comp: Commands, enter: "fade" },
  { id: "pipeline", label: "Pipeline", frames: 270, Comp: Pipeline, enter: "slideRight" },
  { id: "swarm", label: "Swarm", frames: 270, Comp: Swarm, enter: "wipeLeft" },
  { id: "hypothesis", label: "Reasoning", frames: 300, Comp: Hypothesis, enter: "fade" },
  { id: "debate", label: "Council", frames: 330, Comp: Debate, enter: "slideRight" },
  { id: "genome", label: "Genome", frames: 300, Comp: Genome, enter: "wipeLeft" },
  { id: "gate", label: "Zero-day", frames: 390, Comp: DecisionGate, enter: "slideBottom" },
  { id: "verify", label: "Verify", frames: 300, Comp: VerifyGate, enter: "fade" },
  { id: "compare", label: "Compare", frames: 300, Comp: Compare, enter: "wipeLeft" },
  { id: "local", label: "Local-first", frames: 150, Comp: LocalFirst, enter: "fade" },
  { id: "cta", label: "Get started", frames: 180, Comp: CTA, enter: "fade" },
];

export const TOTAL_FRAMES = DECK.reduce((a, s) => a + s.frames, 0) - T * (DECK.length - 1);

// Each scene starts where the previous one ends minus the transition overlap.
export const SECTIONS: readonly (Section & { readonly id: string })[] = DECK.map((s, i) => ({
  id: s.id,
  label: s.label,
  from: DECK.slice(0, i).reduce((a, d) => a + d.frames, 0) - T * i,
}));

export const CyphexLaunch: React.FC = () => {
  return (
    <AbsoluteFill>
      <Backdrop />
      <TransitionSeries>
        {DECK.flatMap(({ id, frames, Comp, enter }) => [
          ...(enter ? [ENTER[enter](`${id}-in`)] : []),
          <TransitionSeries.Sequence key={id} name={id} durationInFrames={frames}>
            <Comp />
          </TransitionSeries.Sequence>,
        ])}
      </TransitionSeries>
      <DeckChrome sections={SECTIONS} />
      <Voiceover sections={SECTIONS} />
    </AbsoluteFill>
  );
};
