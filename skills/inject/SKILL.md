---
name: inject
description: Prepend the current signature.json to Claude's context so code suggestions can mirror the user's style (Claude reads the signature each prompt and decides how closely to follow). INJECT-CONTEXT tier — see `skills/enforce/SKILL.md` + README "Architecture: Inject + Act" for the v2 force-mechanic. Auto-fires on every UserPromptSubmit via plugin hook; also invokable manually as `/cogsig inject`.
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

## Cross-link: enforcement layer (v2)

Inject puts the signature into Claude's context. The `enforce` skill (shipped
2026-04-25) closes the inject-vs-act gap: a `PreToolUse:Edit|Write|MultiEdit`
hook checks every proposed file change against the active signature and warns
or rejects per the user-selected mode (`off` / `warn` / `reject`, default
`warn`). See `skills/enforce/SKILL.md` for details.

Inject = make Claude aware. Enforce = make the awareness load-bearing.

## Status
- [x] SKILL.md + CLI (Day 1)
- [x] plugin API hook — shipped 2026-04-24 via `hooks/user-prompt-submit.sh`
- [x] toggle-aware on/off gating (inject.py respects `state.enabled`)
- [x] pending-patterns surface (power/team/enterprise presets)
- [x] normie-preset suppress (silent auto-promote via review.py)
- [x] v2 enforcement layer cross-linked — see `skills/enforce/SKILL.md`
