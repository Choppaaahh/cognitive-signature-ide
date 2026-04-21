---
name: toggle
description: Slash command to enable, disable, or diff the cognitive signature injection.
---

# toggle — /cogsig slash command

## When invoked
- User types `/cogsig on` | `/cogsig off` | `/cogsig diff` | `/cogsig status`

## What it does (Day 3 target)
- `on` — write `enabled: true` to `.signature-cache/state.json`
- `off` — write `enabled: false`
- `diff` — request three variants of next suggestion: (a) with user's signature injected, (b) with a generic placeholder signature, (c) no injection — render side-by-side
- `status` — print current state, signature version, last update timestamp
- `extract` — force re-extraction (routes to extract skill)
- `capture` — force re-capture (routes to capture skill)

## What it does NOT do
- Does not modify signature.json itself — only state toggles

## Status
- [x] SKILL.md stub (Day 1)
- [ ] command handler (Day 3)
