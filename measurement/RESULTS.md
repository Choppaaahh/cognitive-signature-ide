# Measurement Results — Cognitive Signature IDE

Two measurements. One objective (automated). One architectural (team simulation).

---

## 1. Auto-scorer — 100% accuracy vs 33% chance

**Method**: For each of the 10 dialogue prompts in `prompts_directing.json`, Claude generated 3 outputs: baseline (no signature), placebo (fake signature with opposite traits), real (user's extracted directing-signature). A separate Claude conversation was given the real signature + the 3 shuffled outputs and asked to predict which was produced WITH the signature injected. Compared to ground truth.

**Result**:

| Metric | Value |
|--------|-------|
| Prompts scored | **10/10** |
| Correct predictions | **10** |
| Auto-scorer accuracy | **100.0%** |
| Chance baseline | 33.3% |
| **Delta over chance** | **+66.7pp** |

Every prediction was correct. Confidence varied (0.4 – 0.85), but the judge's direction was never wrong on this signature + prompt set.

**Why this matters**: the test doesn't require user self-scoring. A different Claude, given only the signature and 3 outputs, can reliably pick which output was generated under the signature's influence. That means the signature carries observable, reproducible features — not a felt-sense phenomenon.

**Reproduce**:
```bash
export ANTHROPIC_API_KEY=sk-ant-...
python3 skills/init/init.py --yes                   # auto-seed from your Claude Code history
python3 measurement/blind_test.py --signature signature.json \
    --prompts measurement/prompts_directing.json \
    --out measurement/blind_outputs_directing
python3 measurement/score_auto.py --signature signature.json \
    --outputs measurement/blind_outputs_directing \
    --prompts measurement/prompts_directing.json
```

Raw per-prompt data: `measurement/results_auto_directing.json`.

---

## 2. Team simulation — 5 distinct signatures from same pipeline

**Method**: Four synthetic personas generated via Opus with explicit voice prompts (terse engineer / verbose PM / casual lowercase / formal academic). Each persona's 25-directive corpus ingested + extracted through the same `dialogue_ingest` + `extract --domain directing` pipeline used for the real user. Fifth signature: the real user's signature already extracted from their Claude Code session history.

**Result**: each of the 5 signatures has visibly distinct vocabulary, compression ratio, energy baseline, reframe pattern, and capitalization style. The architecture correctly differentiated all 5 voices.

See `measurement/signature-grid.md` for the full side-by-side.

**Abbreviated**:

| Persona | Top vocabulary | Compression | Energy |
|---------|----------------|-------------|--------|
| Alice (terse) | wdyt, lgtm, yolo, yagni | 55 chars (extreme-terse) | neutral |
| Bob (verbose PM) | circling back, loop in, scope creep | 180 chars (moderate) | neutral |
| Tim (casual) | u, ur, rn, lil, kinda, sooo | 95 chars (terse) | variable |
| Sue (formal) | pursuant to, behooves, posit, contend | 175 chars (verbose) | low |
| **Flex (real)** | laddy, buddy, claudi, hellyea, fire | 420 chars (verbose) | **high** |

The real user's row is extracted from actual Claude Code session JSONLs — "top of the morning my claudius" is a literal captured opening.

**Why this matters**: the plugin generalizes across voices. One pipeline, N users, N distinct signatures. Team deployments (small + enterprise) get per-user differentiation for free.

**Reproduce**:
```bash
export ANTHROPIC_API_KEY=sk-ant-...
python3 measurement/simulate_team.py --directives-per-persona 25
# → generates 4 synthetic persona corpora, extracts signatures,
#   reads your real signature, writes signature-grid.md
```

---

## Honest caveats

- **N=10 prompts is small.** The 100% auto-scorer result has a wide confidence interval. It's directional evidence, not a definitive effect-size estimate. A scaled-up run (N=50+) would tighten this. Treat 100% as "very strong directional signal," not "zero noise."
- **The auto-scorer and the signature-generator share the same model family** (Opus 4.7 both ends). This introduces a model-coherence bias: Claude is likely better at recognizing its own output patterns than a neutral third party would be. Results would differ with a different judge model.
- **The synthetic personas are obviously synthetic.** They're included to demonstrate architectural generalization, not to claim equivalence with real users. Labeled clearly in the grid.
- **The real user's signature was extracted from ~80 directives across Claude Code session history.** Heavier/longer corpora produce more confident signatures. Users with sparse histories should expect weaker dimensions until more usage accrues.
- **Both measurements are internal to this hackathon submission.** Not a peer-reviewed study. Published as evidence of working architecture; replicable via the commands above.
