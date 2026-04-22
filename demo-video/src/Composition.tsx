import { AbsoluteFill, Sequence } from 'remotion';
import { Beat1Hero } from './scenes/Beat1_Hero';
import { Beat2SideBySide } from './scenes/Beat2_SideBySide';
import { Beat3Grid } from './scenes/Beat3_Grid';
import { Beat4Close } from './scenes/Beat4_Close';

export const CogsigDemo: React.FC = () => {
  return (
    <AbsoluteFill style={{ backgroundColor: '#0b0d12', fontFamily: 'monospace' }}>
      <Sequence from={0} durationInFrames={750}>
        <Beat1Hero />
      </Sequence>
      <Sequence from={750} durationInFrames={1800}>
        <Beat2SideBySide />
      </Sequence>
      <Sequence from={2550} durationInFrames={1050}>
        <Beat3Grid />
      </Sequence>
      <Sequence from={3600} durationInFrames={900}>
        <Beat4Close />
      </Sequence>
    </AbsoluteFill>
  );
};
