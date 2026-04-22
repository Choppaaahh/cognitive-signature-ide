import { Composition } from 'remotion';
import { CogsigDemo } from './Composition';

// Total duration: ~150s (2:30) at 30fps = 4500 frames
// Beat 1 (hero):        0-25s   (0-750)      — 750 frames
// Beat 2 (side-by-side): 25-85s  (750-2550)  — 1800 frames
// Beat 3 (grid):        85-120s (2550-3600) — 1050 frames
// Beat 4 (close):       120-150s (3600-4500) — 900 frames

export const Root: React.FC = () => {
  return (
    <>
      <Composition
        id="CogsigDemo"
        component={CogsigDemo}
        durationInFrames={4500}
        fps={30}
        width={1920}
        height={1080}
      />
    </>
  );
};
