import { AbsoluteFill, useCurrentFrame, interpolate, spring, useVideoConfig } from 'remotion';

interface TerminalProps {
  title: string;
  lines: string[];
  startFrame: number;
  linesPerSecond?: number;
  width?: string | number;
  accentColor?: string;
}

export const Terminal: React.FC<TerminalProps> = ({
  title,
  lines,
  startFrame,
  linesPerSecond = 5,
  width = '48%',
  accentColor = '#3ea6ff',
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const elapsed = Math.max(0, frame - startFrame);
  const linesRevealed = Math.floor((elapsed / fps) * linesPerSecond);

  return (
    <div
      style={{
        width,
        height: '85%',
        backgroundColor: '#0f1117',
        border: `2px solid ${accentColor}`,
        borderRadius: 8,
        padding: 24,
        boxSizing: 'border-box',
        boxShadow: `0 0 40px ${accentColor}30`,
        overflow: 'hidden',
        display: 'flex',
        flexDirection: 'column',
      }}
    >
      <div
        style={{
          color: accentColor,
          fontSize: 22,
          fontWeight: 700,
          marginBottom: 16,
          borderBottom: `1px solid ${accentColor}80`,
          paddingBottom: 8,
          letterSpacing: 1,
        }}
      >
        {title}
      </div>
      <div style={{ color: '#e5e7eb', fontSize: 18, lineHeight: 1.6, whiteSpace: 'pre-wrap' }}>
        {lines.slice(0, Math.min(linesRevealed, lines.length)).map((line, i) => (
          <div key={i} style={{ opacity: 1 }}>
            {line}
          </div>
        ))}
        {linesRevealed < lines.length && (
          <span style={{ color: accentColor, animation: 'blink 1s infinite' }}>▊</span>
        )}
      </div>
    </div>
  );
};
