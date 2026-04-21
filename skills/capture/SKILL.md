---
name: capture
description: Sample recent code the user has written — most-recent commits + recent file edits — and stage them for signature extraction.
---

# capture — stage code samples for signature extraction

## When invoked
- On session start if `.signature-cache/` is empty or >24h stale
- Manually via `/cogsig capture`
- Triggered by `extract` skill if no cache exists

## What it does (Day 2 target)
1. Collect last N commits authored by the user (`git log --author=$GIT_USER_EMAIL -n 50 --name-only`)
2. Collect last M files modified in working tree
3. Read 3-5 representative samples per file (function-level if possible)
4. Write to `.signature-cache/samples.json` with `{path, language, content, modified_ts}` rows
5. Emit summary: N samples / M languages / K lines cached

## What it does NOT do
- Does not call the API (extract's job)
- Does not persist samples beyond `.signature-cache/` (gitignored — signature is user-local)
- Does not interpret or analyze — that's extract

## Output
`.signature-cache/samples.json` — ready for extract.

## Status
- [x] SKILL.md stub (Day 1)
- [ ] implementation (Day 2)
