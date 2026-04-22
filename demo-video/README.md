# CogSig Demo Video — Remotion

Programmatic 1920×1080 demo video, ~2:30 total, 4 beats.

**Built with Opus 4.7 hackathon submission (Cerebral Valley + Anthropic).** Data-bound to real signature outputs from the parent repo — the video is literally rendered FROM the pipeline it describes.

## Beats

| Beat | Duration | Content |
|------|----------|---------|
| 1. Hero | 0:00–0:25 | Tagline fade-in, install command with streaming output, "signature active" |
| 2. Side-by-side | 0:25–1:25 | Same prompt, two terminals (naked vs CogSig), response delta live |
| 3. Grid | 1:25–2:00 | 5-persona signature grid (4 synthetic + real), cards animate in staggered |
| 4. Close | 2:00–2:30 | Auto-scorer 100% card, governance-catches scroll (5 real catches), final tagline + URL |

## Install + preview

```bash
cd demo-video
npm install
npm run dev          # opens Remotion Studio at http://localhost:3000
```

## Render MP4

```bash
npm run build        # renders to out/demo.mp4 (h264, 1080p30)
```

## Structure

```
demo-video/
├── package.json           ← Remotion + React deps
├── remotion.config.ts     ← Remotion config
├── tsconfig.json
└── src/
    ├── index.ts           ← registerRoot entry point
    ├── Root.tsx           ← Composition registration (4500 frames @ 30fps)
    ├── Composition.tsx    ← 4-beat Sequence orchestration
    ├── components/        ← Reusable: Terminal / SignatureCard / MeasurementCard / CatchCard
    ├── data/              ← REAL data from parent repo pipeline
    │   ├── signatures.json   ← 5-persona grid data (from simulate_team.py)
    │   ├── sideBySide.json   ← Beat 2 terminal content (from blind_test Opus outputs)
    │   └── catches.json      ← Governance catches (from README live-examples)
    └── scenes/            ← One per beat
        ├── Beat1_Hero.tsx
        ├── Beat2_SideBySide.tsx
        ├── Beat3_Grid.tsx
        └── Beat4_Close.tsx
```

## Customizing

- **Change pacing**: edit frame counts in `Composition.tsx` and per-scene `interpolate()` calls
- **Replace data**: overwrite files in `src/data/`. Video re-renders with new content.
- **Add a beat**: create new scene in `src/scenes/`, register in `Composition.tsx` with new `<Sequence>`
- **Change style**: Terminal / SignatureCard / MeasurementCard / CatchCard are self-contained styled components — edit to taste

## Audio / voiceover

Remotion doesn't record narration; layer in post:
- Record voiceover separately (Loom / QuickTime audio-only / phone recorder)
- Edit over the rendered MP4 in Descript / iMovie / CapCut / etc
- Or use `<Audio>` in Remotion if you have a pre-recorded audio file to mix in programmatically

## Why Remotion for this

- **Data-bound**: the video reads from the same signature files the parent pipeline produces. Update the pipeline, re-render the video. Self-synchronizing.
- **Reproducible**: anyone with node + npm can render bit-identical output. No screen-capture drift.
- **Composable**: scenes are React components. Easy to swap, reorder, extend.
- **Transitions-as-first-class**: spring/interpolate primitives make polished animation one-liner.

## Known limitations

- Video renders from data files, not live from the plugin — if `simulate_team.py` produces different output, update `src/data/signatures.json` accordingly
- No audio track baked in (intentional — add in post)
- Browser-rendered fonts; ensure monospace font stack renders cleanly in your terminal region
