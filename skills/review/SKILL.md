---
name: review
description: Pattern-review surface for pending patterns. After extraction, diff new-signature vs permanent-signature — items at instance_count ≥ 2 not already in permanent become "pending." User approves / rejects / edits via slash commands, OR Claude surfaces them inline via inject.py next-response context.
user-invocable: true
allowed-tools: [Bash, Read, Write]
---

# review — pattern review + approve/reject surface

The plugin's hands-off-by-default UX has a load-bearing exception: when new patterns hit the n=2 promotion threshold, users need a chance to approve / reject / edit them before they enter the permanent signature. This skill manages that queue.

## When invoked

- After `/cogsig extract` runs, review.py auto-diffs new signature vs permanent → writes pending_patterns.json
- `/cogsig pending` — list pending patterns with evidence
- `/cogsig approve 1,3` — promote listed IDs to permanent signature
- `/cogsig reject 2` — reject pattern 2, log to rejected_patterns.jsonl (prevents re-propose)
- `/cogsig edit 1 "new description"` — edit pattern before accepting
- `/cogsig review` — interactive walkthrough (future)

## What it does NOT do

- Doesn't run extraction — that's `extract.py`'s job
- Doesn't inject signatures — that's `inject.py`'s job
- Doesn't auto-promote without user decision — the whole point is human-in-the-loop for pattern-level decisions that permanent signature stores forever

## Integration with inject

`inject.py` reads both `signature.json` (permanent) AND `.signature-cache/pending_patterns.json`. If pending list is non-empty, appends a "PENDING PATTERN REVIEWS" section to the context prefix with voice-matched instructions to surface each pending pattern naturally in the next Claude response. User then replies in chat; approval goes through `/cogsig approve <id>`.

## Preset behavior (from state.json)

Setup-wizard preset determines surface behavior:
- `preset: normie` — auto-promote at n=2 without surfacing (silent)
- `preset: power` — surface before promotion, user approves inline (default)
- `preset: team` — power mode + team-lead audit trail
- `preset: enterprise` — team mode + Managed Agents reviews every promotion

## Data files

- `.signature-cache/pending_patterns.json` — queue of patterns awaiting user decision
- `.signature-cache/rejected_patterns.jsonl` — append-only log of rejections (prevents re-propose)
- `.signature-cache/state.json` — stores active preset and whether pending-surface is enabled
