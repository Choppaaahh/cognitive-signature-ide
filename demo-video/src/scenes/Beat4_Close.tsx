import { AbsoluteFill, useCurrentFrame, interpolate, Sequence } from 'remotion';
import { MeasurementCard } from '../components/MeasurementCard';
import { CatchCard } from '../components/CatchCard';
import catchesData from '../data/catches.json';

export const Beat4Close: React.FC = () => {
  const frame = useCurrentFrame();

  // Section 1 (0-300): measurement card
  // Section 2 (300-600): governance catches scroll
  // Section 3 (600-900): final tagline + URL

  const measurementVisible = frame < 350;
  const catchesVisible = frame >= 300 && frame < 650;
  const closeVisible = frame >= 600;

  const taglineOpacity = interpolate(frame, [620, 700], [0, 1], { extrapolateRight: 'clamp' });
  const urlOpacity = interpolate(frame, [750, 830], [0, 1], { extrapolateRight: 'clamp' });

  return (
    <AbsoluteFill
      style={{
        padding: 60,
        flexDirection: 'column',
        justifyContent: 'center',
        alignItems: 'center',
      }}
    >
      {measurementVisible && (
        <Sequence from={0} durationInFrames={350}>
          <AbsoluteFill style={{ justifyContent: 'center', alignItems: 'center' }}>
            <MeasurementCard
              headline="10 / 10"
              delta="+66.7pp over chance"
              chance="33.3%"
              subtext="Claude-as-judge ran over 10 dialogue prompts with 3 conditions each (baseline / placebo-signature / real-signature). Every prediction correct. No human in the loop. Signature effect is observable and reproducible."
              startFrame={0}
            />
          </AbsoluteFill>
        </Sequence>
      )}

      {catchesVisible && (
        <Sequence from={300} durationInFrames={350}>
          <AbsoluteFill
            style={{
              flexDirection: 'column',
              justifyContent: 'center',
              alignItems: 'center',
              padding: 40,
            }}
          >
            <div
              style={{
                color: '#f59e0b',
                fontSize: 32,
                marginBottom: 30,
                letterSpacing: 2,
                textAlign: 'center',
              }}
            >
              GOVERNANCE CATCHES DURING THIS BUILD
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 14, width: '100%', alignItems: 'center' }}>
              {catchesData.catches.map((c, i) => (
                <CatchCard
                  key={i}
                  agent={c.agent}
                  catch_={c.catch_}
                  outcome={c.outcome}
                  startFrame={i * 30}
                />
              ))}
            </div>
          </AbsoluteFill>
        </Sequence>
      )}

      {closeVisible && (
        <Sequence from={600} durationInFrames={300}>
          <AbsoluteFill
            style={{
              justifyContent: 'center',
              alignItems: 'center',
              flexDirection: 'column',
              padding: 40,
            }}
          >
            <div
              style={{
                opacity: taglineOpacity,
                textAlign: 'center',
                color: '#f4f4f5',
                fontSize: 42,
                lineHeight: 1.4,
                maxWidth: 1400,
              }}
            >
              Claude quietly syncs to your cognitive signature.
              <br />
              <span style={{ color: '#00e8a0' }}>Your Claude perma-remembers what's promoted.</span>
              <br />
              3 deploy modes — solo, team, enterprise.
            </div>
            <div
              style={{
                opacity: urlOpacity,
                color: '#3ea6ff',
                fontSize: 30,
                marginTop: 60,
                fontFamily: 'monospace',
              }}
            >
              github.com/Choppaaahh/cognitive-signature-ide
            </div>
            <div
              style={{
                opacity: urlOpacity,
                color: '#9ca3af',
                fontSize: 20,
                marginTop: 20,
                letterSpacing: 2,
              }}
            >
              BUILT WITH OPUS 4.7 · MIT
            </div>
          </AbsoluteFill>
        </Sequence>
      )}
    </AbsoluteFill>
  );
};
