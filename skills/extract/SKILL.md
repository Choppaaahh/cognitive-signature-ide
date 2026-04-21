---
name: extract
description: Call Opus 4.7 on cached code samples to produce a structured signature.json capturing the user's coding style.
---

# extract — code samples → signature.json

## When invoked
- After `capture` populates `.signature-cache/samples.json`
- Manually via `/cogsig extract`
- Triggered by `inject` skill if signature.json is missing or stale

## What it does (Day 2 target)
1. Load `.signature-cache/samples.json`
2. Compose a prompt asking Opus 4.7 to extract 6 signature dimensions:
   - **naming_convention** — snake_case / camelCase / kebab-case / mixed; preference intensity
   - **comment_density** — comments per 100 lines, docstring presence, inline vs block
   - **function_length** — p50 / p90 / max line counts
   - **error_handling** — try/except style, validation pattern, bare-except tolerance
   - **import_organization** — grouping, ordering, aliasing preferences
   - **structural_preference** — flat vs nested, early-return pattern, helper extraction threshold
3. Opus 4.7 returns JSON matching `signature_schema.json`
4. Validate (QA skill) + persist to `signature.json` at repo root
5. Append to `signature_history.jsonl` for drift tracking

## What it does NOT do
- Does not inject — that's inject's job
- Does not judge "good" or "bad" style — it describes, it doesn't prescribe

## Output
- `signature.json` — current signature, overwrites on each run
- `signature_history.jsonl` — append-only drift log

## Status
- [x] SKILL.md stub (Day 1)
- [ ] signature_schema.json (Day 2)
- [ ] implementation (Day 2)
