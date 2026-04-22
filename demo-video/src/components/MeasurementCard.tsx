import { useCurrentFrame, spring, useVideoConfig, interpolate } from 'remotion';

interface MeasurementCardProps {
  headline: string;
  delta: string;
  chance: string;
  subtext: string;
  startFrame: number;
}

export const MeasurementCard: React.FC<MeasurementCardProps> = ({
  headline,
  delta,
  chance,
  subtext,
  startFrame,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const progress = spring({
    frame: frame - startFrame,
    fps,
    config: { damping: 180, stiffness: 120 },
  });
  const opacity = interpolate(progress, [0, 1], [0, 1]);
  const scale = interpolate(progress, [0, 1], [0.92, 1]);

  return (
    <div
      style={{
        width: '70%',
        backgroundColor: '#0f1117',
        border: '3px solid #00e8a0',
        borderRadius: 16,
        padding: 60,
        boxSizing: 'border-box',
        boxShadow: '0 0 80px #00e8a080',
        opacity,
        transform: `scale(${scale})`,
        textAlign: 'center',
        fontFamily: 'monospace',
      }}
    >
      <div style={{ color: '#9ca3af', fontSize: 26, marginBottom: 20, letterSpacing: 2 }}>
        AUTO-SCORER
      </div>
      <div
        style={{
          color: '#00e8a0',
          fontSize: 140,
          fontWeight: 900,
          lineHeight: 1,
          letterSpacing: -2,
        }}
      >
        {headline}
      </div>
      <div style={{ color: '#e5e7eb', fontSize: 32, marginTop: 10 }}>vs chance {chance}</div>
      <div
        style={{
          color: '#00e8a0',
          fontSize: 46,
          marginTop: 30,
          fontWeight: 700,
        }}
      >
        {delta}
      </div>
      <div style={{ color: '#9ca3af', fontSize: 20, marginTop: 30, lineHeight: 1.5, maxWidth: 700, margin: '30px auto 0' }}>
        {subtext}
      </div>
    </div>
  );
};
