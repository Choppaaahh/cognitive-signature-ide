---
name: export
description: Write a shareable signature JSON from the current signature.json. Stamps origin=self and optional team_id.
user-invocable: true
allowed-tools: [Bash, Read, Write]
---

# export — signature.json → shareable file

## When invoked
- User runs `/cogsig export`
- User runs `/cogsig export --team-id my-team`
- User wants to share their signature with a collaborator

## What it does
1. Load `signature.json` from repo root
2. Stamp `origin: "self"` and `exported_ts` (ISO timestamp)
3. Optionally stamp `team_id` if `--team-id` flag provided
4. Write `signature_export.json` (or path from `--out`)

## What it does NOT do
- Does not modify `signature.json`
- Does not upload anywhere — file-based only

## Output
- `signature_export.json` — shareable, self-contained signature file

## Usage
```bash
python3 skills/export/export.py
python3 skills/export/export.py --out my_sig.json --team-id acme-corp
```
