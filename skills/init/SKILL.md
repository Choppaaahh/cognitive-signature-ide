---
name: init
description: One-command auto-seed from Claude Code session history. Scans ~/.claude/projects/**/*.jsonl, aggregates user-typed directives, runs extract → signature.json active. The default onboarding path.
user-invocable: true
allowed-tools: [Bash, Read, Write]
---

# init — one-command onboarding

The default first-run experience for CogSig. Scans the user's existing Claude Code session history, aggregates user-typed directives into a dialogue corpus, runs extraction → signature active. Zero file-hunting, zero corpus preparation.

## When invoked

- User runs `/cogsig init` as their first plugin command
- `--yes` skips confirmation (for scripted setup)
- `--no-seed` creates empty state for cold-start users
- `--claude-projects PATH` overrides the default `~/.claude/projects` scan location

## What it does

1. Glob `~/.claude/projects/**/*.jsonl`
2. Report discovery: *"Found N sessions across M projects with ~K directives"*
3. Confirm (or skip if `--yes`)
4. Aggregate user-typed directives via `dialogue_ingest` with Claude Code native format
5. Invoke `extract --domain directing`
6. Invoke advisor consultation if confidence thresholds hit
7. Report: signature active + dimensions summary

## What it does NOT do

- Does not upload anything
- Does not modify session JSONLs
- Does not persist beyond the signature + `.signature-cache/` outputs
- Does not auto-push to team or share — that's `/cogsig export`

## Output

- `.signature-cache/samples.json` — aggregated user-directive corpus
- `signature.json` — active signature
- `.signature-cache/signature_history.jsonl` — first history entry
- Optional `.signature-cache/advisor_reports/*.json` if advisor consulted
