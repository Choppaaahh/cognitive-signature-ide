import { AbsoluteFill, useCurrentFrame, interpolate } from 'remotion';
import { SignatureCard } from '../components/SignatureCard';
import signaturesData from '../data/signatures.json';

export const Beat3Grid: React.FC = () => {
  const frame = useCurrentFrame();
  const titleOpacity = interpolate(frame, [0, 30], [0, 1], { extrapolateRight: 'clamp' });

  // Cards fade in staggered — 20 frames apart
  const cardStart = 60;
  const cardStagger = 30;

  const captionOpacity = interpolate(frame, [800, 900], [0, 1], { extrapolateRight: 'clamp' });

  return (
    <AbsoluteFill style={{ padding: 60, flexDirection: 'column' }}>
      <div
        style={{
          opacity: titleOpacity,
          color: '#3ea6ff',
          fontSize: 36,
          textAlign: 'center',
          marginBottom: 10,
          letterSpacing: 2,
        }}
      >
        ONE PIPELINE. FIVE VOICES.
      </div>
      <div
        style={{
          opacity: titleOpacity,
          color: '#9ca3af',
          fontSize: 22,
          textAlign: 'center',
          marginBottom: 40,
        }}
      >
        Four synthetic personas + the real user. Same architecture extracts five visibly-distinct signatures.
      </div>

      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(3, 1fr)',
          gap: 20,
          flex: 1,
          alignContent: 'start',
        }}
      >
        {signaturesData.personas.map((p, i) => (
          <SignatureCard
            key={p.label}
            label={p.label}
            vocab={p.vocab}
            compression={p.compression}
            energy={p.energy}
            directiveStyle={p.directive_style}
            opening={p.opening}
            startFrame={cardStart + i * cardStagger}
            isReal={p.isReal}
          />
        ))}
      </div>

      <div
        style={{
          opacity: captionOpacity,
          color: '#00e8a0',
          fontSize: 24,
          textAlign: 'center',
          marginTop: 20,
          fontStyle: 'italic',
          maxWidth: 1400,
          alignSelf: 'center',
        }}
      >
        The real user's row was extracted from actual Claude Code session JSONLs — "top of the
        morning my claudius" is a literal captured opening.
      </div>
    </AbsoluteFill>
  );
};
