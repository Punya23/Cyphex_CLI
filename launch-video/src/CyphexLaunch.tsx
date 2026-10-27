import { AbsoluteFill } from "remotion";
import { TransitionSeries, linearTiming } from "@remotion/transitions";
import { fade } from "@remotion/transitions/fade";
import { slide } from "@remotion/transitions/slide";
import { wipe } from "@remotion/transitions/wipe";
import { Backdrop } from "./components/Backdrop";
import { DeckChrome, type Section } from "./components/DeckChrome";
import { Voiceover } from "./components/Voiceover";
import { Compare } from "./scenes/Compare";
import { CTA } from "./scenes/CTA";
import { DecisionGate } from "./scenes/DecisionGate";
import { LogoReveal } from "./scenes/LogoReveal";
import { Problem } from "./scenes/Problem";
import {
  RealArena,
  RealChat,
  RealConnect,
  RealCouncil,
  RealGenome,
  RealHypothesis,
  RealIntro,
  RealPatch,
  RealScan,
  RealSheet,
  RealSwarm,
} from "./scenes/Real";
import { VerifyGate } from "./scenes/VerifyGate";

export const T = 12; // transition length, frames

const timing = linearTiming({ durationInFrames: T });

// Transition INTO a scene, by name (the presentation types don't unify).
const ENTER = {
  fade: (key: string) => (
    <TransitionSeries.Transition
      key={key}
      presentation={fade()}
      timing={timing}
    />
  ),
  slideRight: (key: string) => (
    <TransitionSeries.Transition
      key={key}
      presentation={slide({ direction: "from-right" })}
      timing={timing}
    />
  ),
  slideBottom: (key: string) => (
    <TransitionSeries.Transition
      key={key}
      presentation={slide({ direction: "from-bottom" })}
      timing={timing}
    />
  ),
  wipeLeft: (key: string) => (
    <TransitionSeries.Transition
      key={key}
      presentation={wipe({ direction: "from-left" })}
      timing={timing}
    />
  ),
} as const;

// One row per scene, in playback order. `enter` is the transition INTO the scene.
// Voiceover anchors in components/Voiceover.tsx refer to a scene by its `id`.
// Scenes named Real* play the screen recordings (public/footage, built by the ffmpeg
// script from the original .mov files); the rest are motion graphics.
const DECK: readonly {
  readonly id: string;
  readonly label: string;
  readonly frames: number;
  readonly Comp: React.FC;
  readonly enter?: keyof typeof ENTER;
}[] = [
  { id: "intro", label: "Intro", frames: 165, Comp: RealIntro },
  {
    id: "problem",
    label: "Problem",
    frames: 135,
    Comp: Problem,
    enter: "fade",
  },
  {
    id: "logo",
    label: "Product",
    frames: 150,
    Comp: LogoReveal,
    enter: "fade",
  },
  {
    id: "connect",
    label: "Webhook",
    frames: 225,
    Comp: RealConnect,
    enter: "fade",
  },
  { id: "scan", label: "Scan", frames: 270, Comp: RealScan, enter: "fade" },
  {
    id: "swarm",
    label: "Agents",
    frames: 280,
    Comp: RealSwarm,
    enter: "slideRight",
  },
  {
    id: "hypothesis",
    label: "Reasoning",
    frames: 360,
    Comp: RealHypothesis,
    enter: "fade",
  },
  {
    id: "council",
    label: "Council",
    frames: 170,
    Comp: RealCouncil,
    enter: "wipeLeft",
  },
  {
    id: "genome",
    label: "Genome",
    frames: 235,
    Comp: RealGenome,
    enter: "fade",
  },
  {
    id: "arena",
    label: "Attack sim",
    frames: 170,
    Comp: RealArena,
    enter: "slideRight",
  },
  {
    id: "gate",
    label: "Zero-day",
    frames: 300,
    Comp: DecisionGate,
    enter: "slideBottom",
  },
  {
    id: "patch",
    label: "Patching",
    frames: 315,
    Comp: RealPatch,
    enter: "wipeLeft",
  },
  {
    id: "verify",
    label: "Verify",
    frames: 300,
    Comp: VerifyGate,
    enter: "fade",
  },
  {
    id: "sheet",
    label: "Sheets",
    frames: 180,
    Comp: RealSheet,
    enter: "fade",
  },
  {
    id: "chat",
    label: "Chat",
    frames: 200,
    Comp: RealChat,
    enter: "fade",
  },
  {
    id: "compare",
    label: "Compare",
    frames: 255,
    Comp: Compare,
    enter: "wipeLeft",
  },
  { id: "cta", label: "Get started", frames: 180, Comp: CTA, enter: "fade" },
];

export const TOTAL_FRAMES =
  DECK.reduce((a, s) => a + s.frames, 0) - T * (DECK.length - 1);

// Each scene starts where the previous one ends minus the transition overlap.
export const SECTIONS: readonly (Section & { readonly id: string })[] =
  DECK.map((s, i) => ({
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
          <TransitionSeries.Sequence
            key={id}
            name={id}
            durationInFrames={frames}
          >
            <Comp />
          </TransitionSeries.Sequence>,
        ])}
      </TransitionSeries>
      <DeckChrome sections={SECTIONS} />
      <Voiceover sections={SECTIONS} />
    </AbsoluteFill>
  );
};
