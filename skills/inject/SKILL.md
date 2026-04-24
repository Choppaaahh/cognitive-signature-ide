---
name: inject
description: Prepend the current signature.json to Claude's context so code suggestions match the user's style. Auto-fires on every UserPromptSubmit via plugin hook; also invokable manually as `/cogsig inject`.
user-invocable: true
allowed-tools: [Read]
---

# inject — signature → context

## When invoked
- **Automatically** on every Claude Code UserPromptSubmit via `hooks/user-prompt-submit.sh` (fires when `/cogsig on`)
- Skipped entirely if `/cogsig off` (toggle state)
- Silently no-ops if no signature file exists at `.signature-cache/signature.json`
- Manually runnable as `/cogsig inject` or `python3 skills/inject/inject.py --repo <dir>`

## What it does
1. Load `signature.json` for the active scope from `.signature-cache/`
2. Compose a context prefix describing the user's coding signature + any pending patterns surface (power/team/enterprise presets only — normie suppresses)
3. Emit prefix to stdout so the hook flows it into CC's context before reasoning

## What it does NOT do
- Does not extract or re-extract — that's extract's job
- Does not modify Claude's actual suggestions — only primes the input context
- Does not surface pending patterns when preset is `normie` (normie uses silent auto-promote via review.py)

## Toggle states (handled by toggle skill)
- `on` — inject on every prompt (default)
- `off` — no injection; baseline Claude behavior

## Status
- [x] SKILL.md + CLI (Day 1)
- [x] plugin API hook — shipped 2026-04-24 via `hooks/user-prompt-submit.sh`
- [x] toggle-aware on/off gating (inject.py respects `state.enabled`)
- [x] pending-patterns surface (power/team/enterprise presets)
- [x] normie-preset suppress (silent auto-promote via review.py)
