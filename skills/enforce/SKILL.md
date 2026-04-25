---
name: enforce
description: CogSig v2 enforcement layer — convert signature from inject-only to inject+act. PreToolUse hook checks every Edit/Write/MultiEdit against the active signature.json and warns or rejects per the user's selected mode.
user-invocable: true
allowed-tools: [Read, Write]
---

# enforce — CogSig v2 enforcement layer

Closes the inject-vs-act gap diagnosed by a follow-up cite-vs-invoke audit. The
existing `inject` skill puts the signature in front of Claude on every prompt,
but Claude could still produce code that violates the signature with no
consequence. The `enforce` layer fires on `PreToolUse:Edit|Write|MultiEdit`,
detects violations, and (in `reject` mode) blocks the tool call before the file
is touched.

## Modes

| mode    | severity=high | severity=medium | severity=low | default? |
|---------|---------------|-----------------|--------------|----------|
| off     | pass          | pass            | pass         |          |
| warn    | advisory only | advisory only   | advisory only| **YES**  |
| reject  | exit 1 (block)| advisory only   | advisory only|          |

Default is `warn` — start safe, build empirical FP rate, then user opts up to
`reject` once confident. Per-rule severity is set inside
`scripts/check_signature_violations.py` (`RULE_SEVERITY` dict).

## Mode determination order

1. `signature.json` field `enforcement_mode`
2. `.signature-cache/state.json` field `enforcement_mode`
3. fallback: `warn`

## FP-risk knobs

- **enforcement_whitelist** (in signature.json): list of substrings tested
  against the target file path. Any hit → bypass. Use for test directories,
  generated code, vendor/, etc.
- **per-turn pause**: `touch .signature-cache/enforcement_pause` then retry
  the tool call. The hook consumes the flag (auto-deletes) on the next check.
  Or via slash command: `/cogsig pause-enforce`.
- **graceful degrade**: missing or unreadable `signature.json` → exit 0
  silently. Missing `jq` or `python3` → exit 0 silently. The hook never blocks
  on its own infrastructure failures.

## Audit log

Every check (regardless of verdict) is appended to
`~/.claude/cogsig-enforcement-log.jsonl` with provenance trio
(`source: cogsig-pre-tool-use-enforce`, `trigger: PreToolUse:<tool>`,
`trust_tier: scripted`). Use this for post-hoc FP audit:

```
jq 'select(.severity != "none")' ~/.claude/cogsig-enforcement-log.jsonl
```

## Slash commands (handled by toggle.py)

- `/cogsig toggle-enforce <off|warn|reject>` — set the mode
- `/cogsig pause-enforce` — bypass enforcement for the next single tool call

## Rule classes (current)

- **naming_convention** — function names violating `signature.dimensions.naming_convention.primary_style`
- **import_wildcard** — `from x import *` when signature prefers explicit imports
- **bare_except** — bare `except:` when signature `bare_except_tolerance: never|rare`
- **indent_style** — file mixes tab + space leading indent (Python only)
- **structural_nesting_depth** — placeholder, low severity (heuristic, never rejects)

## What this does NOT do

- Does not edit code suggestions — only blocks or warns post-hoc on tool calls
- Does not run for non-Python files (rule set is python-leaning until v3)
- Does not enforce on dialogue/directing-domain signatures (no code markers)
- Does not log or store the proposed file content (only metadata + verdict)

## Honest assessment

Is this enforcement or just better injection? Answer: it's both. The PreToolUse
hook IS act — it can exit 1 and block a tool call. But the rule set is small
(~5 classes). Claims of "enforces signature" are bounded by which dimensions
the detector implements. Future work: extend detector to comment_density,
function_length, structural_preference (deeper AST checks).

## Status

- [x] PreToolUse hook (`hooks/pre-tool-use-enforce.sh`) — shipped 2026-04-25
- [x] Violation detector (`scripts/check_signature_violations.py`) — shipped 2026-04-25
- [x] Mode control (off / warn / reject) — shipped
- [x] FP whitelist + per-turn pause — shipped
- [x] Provenance-logged audit trail — shipped
- [ ] Mode-toggle slash command — wired via toggle.py extension
- [ ] AST-level rule extension (function_length, structural_preference) — v3
