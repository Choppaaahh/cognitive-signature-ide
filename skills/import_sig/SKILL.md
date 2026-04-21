---
name: import
description: Load an imported signature JSON as the active signature. Sets origin=imported so Historian classifies any drift as EXPECTED.
user-invocable: true
allowed-tools: [Bash, Read, Write]
---

# import — load a teammate's signature as the active signature

## When invoked
- User runs `/cogsig import path/to/teammate_sig.json`
- User wants to adopt a shared team signature

## What it does
1. Load and validate the provided signature JSON
2. Override `origin` to `"imported"` and stamp `imported_ts`
3. Write to `signature.json` (becomes the active signature for inject)
4. Append to `signature_history.jsonl` (Historian sees origin=imported and classifies changes as EXPECTED)

## What it does NOT do
- Does not modify the source file
- Does not merge signatures — full replacement only

## Output
- `signature.json` — now holds the imported signature
- `signature_history.jsonl` — import event appended

## Usage
```bash
python3 skills/import_sig/import_sig.py teammate_signature.json
python3 skills/import_sig/import_sig.py /path/to/shared/sig.json --repo /my/project
```
