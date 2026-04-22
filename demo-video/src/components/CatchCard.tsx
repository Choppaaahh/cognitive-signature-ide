import { useCurrentFrame, spring, useVideoConfig, interpolate } from 'remotion';

interface CatchCardProps {
  agent: string;
  catch_: string;
  outcome: string;
  startFrame: number;
}

export const CatchCard: React.FC<CatchCardProps> = ({ agent, catch_, outcome, startFrame }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const progress = spring({
    frame: frame - startFrame,
    fps,
    config: { damping: 200, stiffness: 180 },
  });
  const opacity = interpolate(progress, [0, 1], [0, 1]);
  const translateX = interpolate(progress, [0, 1], [40, 0]);

  return (
    <div
      style={{
        width: '80%',
        backgroundColor: '#0f1117',
        border: '2px solid #f59e0b',
        borderRadius: 10,
        padding: 20,
        boxSizing: 'border-box',
        opacity,
        transform: `translateX(${translateX}px)`,
        display: 'flex',
        flexDirection: 'column',
        gap: 8,
      }}
    >
      <div style={{ color: '#f59e0b', fontSize: 18, fontWeight: 700, letterSpacing: 0.5 }}>
        {agent}
      </div>
      <div style={{ color: '#e5e7eb', fontSize: 20, lineHeight: 1.4 }}>{catch_}</div>
      <div style={{ color: '#9ca3af', fontSize: 16, fontStyle: 'italic' }}>→ {outcome}</div>
    </div>
  );
};
