# measurement/

Blind-test harness for the cogsig Impact claim: **does injecting my signature actually make Claude's output look more like code I'd write?**

## The test

10 prompts × 3 conditions = 30 model outputs.

| Condition | System prompt |
|-----------|---------------|
| baseline | (none — Claude default) |
| placebo | a plausible-but-fake signature with low confidence values |
| real | the user's actual extracted `signature.json` |

The three outputs for each prompt are then **shuffled without labels** and the author picks which is theirs. Accuracy is compared against the 33% chance baseline.

A meaningful signal (say, ≥50% accuracy) is evidence the plugin changes Claude's output in a direction the author recognizes. Chance-level accuracy would mean the signature has no observable effect.

## Run it

```bash
# 1. Make sure you have a real signature
export ANTHROPIC_API_KEY=sk-ant-...
python3 skills/capture/capture.py
python3 skills/extract/extract.py

# 2. Generate 30 outputs (10 prompts × 3 conditions)
python3 measurement/blind_test.py

# 3a. View all 10 prompts with shuffled A/B/C outputs, deterministic seed
python3 measurement/score.py --view
# → reads measurement/blind_view.md at your own pace

# 3b. Record your picks as a comma-separated string (10 picks, one per prompt)
python3 measurement/score.py --picks A,C,B,A,B,C,A,C,B,A --seed 42
# → writes measurement/results.md + results.json

# Alternative: --interactive (TTY only, fails on piped stdin)
python3 measurement/score.py --interactive
```

Output:
- `measurement/blind_outputs/<prompt-id>/{baseline,placebo,real}.md` — raw model outputs (gitignored)
- `measurement/blind_view.md` — shuffled reading view (gitignored — contains your signature signal)
- `measurement/results.md` — headline + per-prompt picks (SHIPS WITH SUBMISSION)
- `measurement/results.json` — machine-readable results (SHIPS WITH SUBMISSION)

## Honest caveats

- **Self-scored.** The author IS the ground truth, which is exactly the claim being tested but also means this is not a double-blind study. For Phase 2 (post-hackathon), a teammate who's seen your code should be able to ID your outputs at similar-or-better than chance.
- **10 prompts is small.** The confidence interval is wide. A 50% result with n=10 is consistent with a "true" accuracy of anywhere from ~25% to ~75% at 95% CI. Treat the result as directional.
- **The placebo is not true zero.** Any signature injected changes output. The cleanest "no-effect" comparison is baseline vs real; placebo catches "does ANY signature at all shift output, or does the right signature shift it specifically?"

## Prompts

See `prompts.json` for the 10 prompts. They're picked to exercise multiple signature dimensions:

- **naming_convention**: function/variable names will expose this
- **comment_density + docstrings**: visible in every output
- **function_length**: verbose-preference vs terse-preference is visible
- **error_handling**: 4+ prompts ask for explicit error handling
- **import_organization**: visible in imports when needed
- **structural_preference**: nesting depth + early-return shows up everywhere

## What ships with the submission

- `results.md` — the headline number + per-prompt breakdown
- `results.json` — the raw data
- `blind_outputs/` is **gitignored** — the raw outputs are user-specific and not shipped
