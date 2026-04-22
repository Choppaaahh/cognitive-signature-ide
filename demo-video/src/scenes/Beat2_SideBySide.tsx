import { AbsoluteFill, useCurrentFrame, interpolate } from 'remotion';
import { Terminal } from '../components/Terminal';
import sideBySideData from '../data/sideBySide.json';

export const Beat2SideBySide: React.FC = () => {
  const frame = useCurrentFrame();

  // Title fades in first
  const titleOpacity = interpolate(frame, [0, 30], [0, 1], { extrapolateRight: 'clamp' });

  // Prompt appears after title
  const promptOpacity = interpolate(frame, [60, 100], [0, 1], { extrapolateRight: 'clamp' });

  // Both terminals render the same prompt then their different response
  // Terminals start typing at frame 180
  const terminalStart = 180;

  const nakedLines = [
    '> ' + sideBySideData.prompt,
    '',
    ...sideBySideData.nakedResponse,
  ];
  const cogsigLines = [
    '> ' + sideBySideData.prompt,
    '',
    ...sideBySideData.cogsigResponse,
  ];

  const captionOpacity = interpolate(frame, [1400, 1500], [0, 1], { extrapolateRight: 'clamp' });

  return (
    <AbsoluteFill style={{ padding: 60, flexDirection: 'column' }}>
      <div
        style={{
          opacity: titleOpacity,
          color: '#3ea6ff',
          fontSize: 32,
          textAlign: 'center',
          marginBottom: 12,
          letterSpacing: 2,
        }}
      >
        SAME PROMPT. TWO CLAUDES.
      </div>
      <div
        style={{
          opacity: promptOpacity,
          color: '#e5e7eb',
          fontSize: 22,
          textAlign: 'center',
          fontStyle: 'italic',
          marginBottom: 30,
        }}
      >
        "{sideBySideData.prompt}"
      </div>

      <div style={{ display: 'flex', justifyContent: 'space-between', flex: 1, gap: 30 }}>
        <Terminal
          title="NAKED CLAUDE"
          lines={nakedLines}
          startFrame={terminalStart}
          linesPerSecond={4}
          accentColor="#6b7280"
          width="49%"
        />
        <Terminal
          title="CLAUDE + COGSIG"
          lines={cogsigLines}
          startFrame={terminalStart}
          linesPerSecond={4}
          accentColor="#00e8a0"
          width="49%"
        />
      </div>

      <div
        style={{
          opacity: captionOpacity,
          color: '#00e8a0',
          fontSize: 30,
          textAlign: 'center',
          marginTop: 30,
          fontWeight: 600,
        }}
      >
        Same information. Radically different shape.
        <span style={{ color: '#9ca3af', fontSize: 22, marginLeft: 20 }}>
          Right column matches the user's voice.
        </span>
      </div>
    </AbsoluteFill>
  );
};
