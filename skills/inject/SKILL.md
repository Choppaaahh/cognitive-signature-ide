---
name: inject
description: Prepend the current signature.json to Claude's context so code suggestions match the user's style.
---

# inject — signature → context

## When invoked
- On every Claude Code prompt if `/cogsig on`
- Skipped entirely if `/cogsig off`
- Manually via `/cogsig inject`

## What it does (Day 3 target)
1. Load `signature.json` from repo root
2. Compose a context prefix: "The user's coding signature: [SIGNATURE]. Match this style in all code suggestions."
3. Inject at system-prompt layer OR append to user's prompt (TBD which is cleaner for Claude Code plugin API)
4. Emit telemetry: signature injected / version / timestamp

## What it does NOT do
- Does not extract or re-extract — that's extract's job
- Does not modify Claude's actual suggestions — only primes the input context

## Toggle states (handled by toggle skill)
- `on` — inject on every prompt
- `off` — no injection (baseline Claude behavior)
- `diff` — special mode: render mine/theirs/generic side-by-side for comparison

## Status
- [x] SKILL.md stub (Day 1)
- [ ] plugin API hook (Day 3)
- [ ] diff mode (Day 3)
