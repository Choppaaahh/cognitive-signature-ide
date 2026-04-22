import { useCurrentFrame, spring, useVideoConfig, interpolate } from 'remotion';

interface SignatureCardProps {
  label: string;
  vocab: string[];
  compression: string;
  energy: string;
  directiveStyle: string;
  opening?: string;
  startFrame: number;
  isReal?: boolean;
}

export const SignatureCard: React.FC<SignatureCardProps> = ({
  label,
  vocab,
  compression,
  energy,
  directiveStyle,
  opening,
  startFrame,
  isReal = false,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const progress = spring({
    frame: frame - startFrame,
    fps,
    config: { damping: 200, stiffness: 150 },
  });
  const opacity = interpolate(progress, [0, 1], [0, 1]);
  const translateY = interpolate(progress, [0, 1], [20, 0]);

  const accent = isReal ? '#00e8a0' : '#3ea6ff';

  return (
    <div
      style={{
        backgroundColor: '#0f1117',
        border: `2px solid ${accent}${isReal ? 'ff' : '80'}`,
        borderRadius: 10,
        padding: 18,
        boxSizing: 'border-box',
        boxShadow: isReal ? `0 0 30px ${accent}60` : `0 0 15px ${accent}30`,
        opacity,
        transform: `translateY(${translateY}px)`,
        display: 'flex',
        flexDirection: 'column',
        gap: 8,
      }}
    >
      <div
        style={{
          color: accent,
          fontSize: 18,
          fontWeight: 700,
          letterSpacing: 0.5,
        }}
      >
        {label}
        {isReal && <span style={{ fontSize: 12, marginLeft: 8 }}>● real</span>}
      </div>
      <div style={{ color: '#9ca3af', fontSize: 13 }}>
        {opening && <div style={{ fontStyle: 'italic' }}>"{opening}"</div>}
      </div>
      <div style={{ color: '#e5e7eb', fontSize: 13, lineHeight: 1.5 }}>
        <div>
          <span style={{ color: '#9ca3af' }}>vocab: </span>
          <span style={{ color: accent }}>{vocab.slice(0, 4).join(', ')}</span>
        </div>
        <div>
          <span style={{ color: '#9ca3af' }}>compression: </span>
          {compression}
        </div>
        <div>
          <span style={{ color: '#9ca3af' }}>energy: </span>
          {energy}
        </div>
        <div>
          <span style={{ color: '#9ca3af' }}>style: </span>
          {directiveStyle}
        </div>
      </div>
    </div>
  );
};
