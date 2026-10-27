import { Audio, Sequence, staticFile } from "remotion";

// ElevenLabs narration (voice: Desmond, eleven_v4). Each line is anchored to a
// scene by its DECK id plus a frame offset so it lands on the matching
// on-screen beat. Placed at the composition level so a line may run a few
// frames past its scene without being cut by the scene's Sequence.
const LINES: readonly { readonly file: string; readonly scene: string; readonly offset: number }[] = [
  { file: "vo01-intro.mp3", scene: "intro", offset: 10 },
  { file: "vo02-problem.mp3", scene: "problem", offset: 12 },
  { file: "vo03-logo.mp3", scene: "logo", offset: 10 },
  { file: "vo11-connect.mp3", scene: "connect", offset: 10 },
  { file: "vo05-pipeline.mp3", scene: "scan", offset: 8 },
  { file: "vo06-swarm.mp3", scene: "swarm", offset: 16 },
  { file: "vo05b-hypothesis.mp3", scene: "hypothesis", offset: 32 },
  { file: "vo06c-council.mp3", scene: "council", offset: 8 },
  { file: "vo07-genome.mp3", scene: "genome", offset: 10 },
  // 12.5s line: starts in the attack-sim scene so its 2nd sentence lands as the gate scene opens
  { file: "vo08a-gate.mp3", scene: "arena", offset: 40 },
  { file: "vo06b-debate.mp3", scene: "patch", offset: 6 },
  { file: "vo07a-verify.mp3", scene: "verify", offset: 20 },
  { file: "vo07b-verify.mp3", scene: "verify", offset: 108 },
  { file: "vo12-sheet.mp3", scene: "sheet", offset: 12 },
  { file: "vo13-chat.mp3", scene: "chat", offset: 10 },
  { file: "vo10-compare.mp3", scene: "compare", offset: 10 },
  { file: "vo09-cta.mp3", scene: "cta", offset: 66 },
];

export const Voiceover: React.FC<{ readonly sections: readonly { readonly id: string; readonly from: number }[] }> = ({
  sections,
}) => (
  <>
    {LINES.map((l) => {
      const section = sections.find((s) => s.id === l.scene);
      if (!section) throw new Error(`Voiceover: unknown scene "${l.scene}" for ${l.file}`);
      return (
        <Sequence key={l.file} from={section.from + l.offset} name={l.file}>
          <Audio src={staticFile(`audio/${l.file}`)} />
        </Sequence>
      );
    })}
  </>
);
