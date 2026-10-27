import { Audio, Sequence, staticFile } from "remotion";
import type { Section } from "./DeckChrome";

// ElevenLabs narration (voice: Desmond, eleven_v4). Each line is anchored to a
// scene by index into SECTIONS plus a frame offset so it lands on the matching
// on-screen beat. Placed at the composition level so a line may run a few
// frames past its scene without being cut by the scene's Sequence.
const LINES: readonly {
  readonly file: string;
  readonly scene: number;
  readonly offset: number;
}[] = [
  { file: "vo01-intro.mp3", scene: 0, offset: 10 },
  { file: "vo02-problem.mp3", scene: 1, offset: 20 },
  { file: "vo03-logo.mp3", scene: 2, offset: 10 },
  { file: "vo04-commands.mp3", scene: 3, offset: 6 },
  { file: "vo05-pipeline.mp3", scene: 4, offset: 8 },
  { file: "vo06-swarm.mp3", scene: 5, offset: 4 },
  { file: "vo07a-verify.mp3", scene: 6, offset: 20 },
  { file: "vo07b-verify.mp3", scene: 6, offset: 108 },
  { file: "vo08-local.mp3", scene: 7, offset: 16 },
  { file: "vo09-cta.mp3", scene: 8, offset: 66 },
];

export const Voiceover: React.FC<{ readonly sections: readonly Section[] }> = ({
  sections,
}) => (
  <>
    {LINES.map((l) => (
      <Sequence
        key={l.file}
        from={sections[l.scene].from + l.offset}
        name={l.file}
      >
        <Audio src={staticFile(`audio/${l.file}`)} />
      </Sequence>
    ))}
  </>
);
