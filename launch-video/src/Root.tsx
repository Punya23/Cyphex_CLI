import { Composition } from "remotion";
import { CyphexLaunch, TOTAL_FRAMES } from "./CyphexLaunch";

export const RemotionRoot: React.FC = () => {
  return (
    <>
      <Composition
        id="CyphexLaunch"
        component={CyphexLaunch}
        durationInFrames={TOTAL_FRAMES}
        fps={30}
        width={1920}
        height={1080}
      />
    </>
  );
};
