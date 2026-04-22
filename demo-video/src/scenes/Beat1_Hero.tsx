import { AbsoluteFill, useCurrentFrame, interpolate, spring, useVideoConfig } from 'remotion';

export const Beat1Hero: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  // Tagline fades in first, then install command appears
  const taglineOpacity = interpolate(frame, [15, 60], [0, 1], {
    extrapolateRight: 'clamp',
  });
  const taglineY = interpolate(frame, [15, 60], [20, 0], { extrapolateRight: 'clamp' });

  const installOpacity = interpolate(frame, [180, 240], [0, 1], { extrapolateRight: 'clamp' });

  const commandProgress = interpolate(frame, [240, 420], [0, 1], { extrapolateRight: 'clamp' });
  const command = '/cogsig init --yes';
  const commandRevealed = command.slice(0, Math.floor(command.length * commandProgress));

  // Output lines fade in sequentially after command
  const outputLines = [
    'scanning ~/.claude/projects/...',
    'found 123 sessions with ~2,400 directives',
    'extracting VOICE signature via Opus 4.7 (directing domain)...',
    'extracting OPERATIONAL signature via Opus 4.7 (operational domain)...',
    'signature active.',
  ];

  const outputsOpacity = (i: number) =>
    interpolate(frame, [450 + i * 40, 480 + i * 40], [0, 1], { extrapolateRight: 'clamp' });

  return (
    <AbsoluteFill
      style={{
        display: 'flex',
        justifyContent: 'center',
        alignItems: 'center',
        flexDirection: 'column',
        padding: 80,
      }}
    >
      <div
        style={{
          opacity: taglineOpacity,
          transform: `translateY(${taglineY}px)`,
          textAlign: 'center',
          maxWidth: 1400,
        }}
      >
        <div style={{ color: '#3ea6ff', fontSize: 28, marginBottom: 20, letterSpacing: 3 }}>
          COGNITIVE SIGNATURE IDE
        </div>
        <div style={{ color: '#f4f4f5', fontSize: 44, lineHeight: 1.3, fontWeight: 400 }}>
          Claude quietly syncs to your cognitive signature —
          <br />
          <span style={{ color: '#00e8a0' }}>voice</span>{' '}
          <span style={{ color: '#9ca3af', fontSize: 32 }}>
            (directives, conversational flow, idiomatic tells)
          </span>
          <br />+{' '}
          <span style={{ color: '#f59e0b' }}>operational patterns</span>{' '}
          <span style={{ color: '#9ca3af', fontSize: 32 }}>
            (failure modes, reasoning chains, recurring decisions)
          </span>
          <br />— and stays aligned as you change.
        </div>
      </div>

      <div style={{ marginTop: 80, opacity: installOpacity, width: '60%' }}>
        <div
          style={{
            backgroundColor: '#0f1117',
            border: '2px solid #3ea6ff',
            borderRadius: 10,
            padding: 24,
            boxShadow: '0 0 30px #3ea6ff40',
          }}
        >
          <div style={{ color: '#3ea6ff', fontSize: 18, marginBottom: 12, letterSpacing: 1 }}>
            ~ first-run setup
          </div>
          <div style={{ color: '#e5e7eb', fontSize: 24, fontFamily: 'monospace' }}>
            $ {commandRevealed}
            {commandProgress < 1 && <span style={{ color: '#3ea6ff' }}>▊</span>}
          </div>
          <div style={{ marginTop: 16, color: '#9ca3af', fontSize: 18, lineHeight: 1.6 }}>
            {outputLines.map((line, i) => (
              <div key={i} style={{ opacity: outputsOpacity(i) }}>
                {line.startsWith('signature active') ? (
                  <span style={{ color: '#00e8a0', fontWeight: 700 }}>✓ {line}</span>
                ) : (
                  line
                )}
              </div>
            ))}
          </div>
        </div>
      </div>
    </AbsoluteFill>
  );
};
