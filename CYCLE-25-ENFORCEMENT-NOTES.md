# CogSig Cycle-25 Enforcement Architecture Notes

**Date:** 2026-04-25
**Context:** Cycle-25 cite-vs-invoke audit refinement (private scaffold, parallel scope) sharpened the distinction between INVOCATION (text appears in context) and EXECUTION (behavior actually changes). CogSig is an instance of the same gap class — this note documents the v2 enforcement architecture being shipped to close it.

---

## The reframe (cycle-25 thesis)

> Hooks that emit imperative prose ("REMEMBER to dispatch X", "RUN vault_search first") count as "invoked" if their stdout reaches CC's context. But CC reads the reminder and decides whether to comply. The reminder is willpower-gated. A hook that calls `exit 1` when `py_compile` fails is the only canonical force-mechanic in the parent scaffold's 24-hook set today.

Source: `~/Flex/Trading/reports/hook_invocation_architecture_audit_2026-04-25.md`

| Architecture tier | Mechanic | Force? |
|---|---|---|
| **REJECT / REWRITE** | Block or modify the tool call before it runs | YES (architectural) |
| **INJECT-CONTEXT** | Prepend curated content (signature.json, vault hits) to context | NO (model decides whether to use it) |
| **INJECT-REMINDER** | Imperative prose ("REMEMBER to do X") | NO (willpower-gated) |
| **PASSIVE-CHECK** | Diagnostic write-only (logs, status reports) | NO (informational) |

Substrate-lock (real enforcement) lives only in tier 1.

---

## CogSig v1 — honest classification

The plugin currently ships 2 hooks:

| Hook | File | Tier | What it does |
|---|---|---|---|
| `SessionStart` | `hooks/session-start.sh` | **PASSIVE-CHECK** | Emits CogSig status block on session open. Diagnostic only. |
| `UserPromptSubmit` | `hooks/user-prompt-submit.sh` | **INJECT-CONTEXT** | Runs `inject.py`, prepends `signature.json` content to CC's context every prompt. CC sees the signature; CC chooses whether to mirror it. |

**Honest CogSig v1 substrate-lock fraction: 0/2 force-mechanics.**

The signature injection IS valuable — INJECT-CONTEXT is structurally stronger than INJECT-REMINDER because it primes Claude with curated content rather than imperative phrasing. But it does NOT enforce. A user can ask the post-injection Claude for a corporate-formal email and Claude will comply, signature notwithstanding.

This is the same architectural shape as the parent-scaffold's 14 INJECT-REMINDER UserPromptSubmit hooks. CogSig was not unique in this gap; it was structurally typical.

### What CogSig v1 GOT RIGHT

Two important caveats keep CogSig from being merely decorative:

1. **The pattern auto-promote gate** — `skills/review/review.py::cmd_approve` runs `_qa_validate_patterns()` BEFORE writing to permanent. Patterns with malformed schema, missing `evidence_list`, or `instance_count < 2` are REJECTED at the code path. **This IS a force-mechanic** — it gates state mutation, not just context. It's tier-1 substrate-lock applied at the pattern-promotion edge of the system. The post-Audit Fix-4 (2026-04-23) installed this gate; the v1 audit framing missed crediting it as enforcement because it lives in a Python function rather than a hook.

2. **CogSig hooks PATTERNS not RULES** — the parent scaffold's gap is that text-only rules ("MUST do X") don't install reflexes; CogSig's primary mechanism injects EXTRACTED PATTERNS (compression ratio, idiomatic tells, vocabulary anchors) — these are descriptive, not imperative. A descriptive injection is closer to a "give Claude better priors" mechanic than a "Claude should remember to" reminder. Stronger by construction.

So the honest CogSig v1 reading is:
- 2 hooks, both INJECT-tier (no reject/rewrite at the hook layer)
- 1 force-mechanic at the pattern-promotion edge (`approve()` QA gate)
- Pattern injection ≠ rule reminder — descriptive injection is structurally stronger than imperative injection

---

## CogSig v2 — the act layer

User reframe (2026-04-25): *"we wanna be injecting AND acting"*.

v2 adds the missing tier-1 force-mechanic at the hook layer:

### New hook: PreToolUse signature-violation detector

Fires on `Edit` / `Write` / `MultiEdit` tool calls. Reads:
- The proposed tool input (the new file content / diff)
- `signature.json` (the active CogSig)
- A signature-violation rule set derived from the signature dimensions

If the proposed write **violates** a confidently-extracted signature dimension (e.g., user signature says `compression: terse`, proposed write produces a 2x-paragraph corporate-style draft), the hook either:

- **WARN** mode (default) — emits a violation receipt to CC's context: `"SIGNATURE-VIOLATION: dimension=compression, signature=terse(0.85), proposed=verbose. Consider revision before write."` Non-blocking; CC may proceed. Surface lets the user catch the divergence inline.
- **REJECT** mode (opt-in) — exits non-zero, blocking the tool call. CC must regenerate aligned with signature, or user must override.

False-positive whitelist:
- Signature dimensions below confidence threshold (default 0.6) DON'T fire.
- Files matching `.cogsig-no-enforce` patterns (e.g., generated code, vendored files) skip the check.
- Tool calls explicitly tagged in their reasoning text with `signature-override:` opt out.

### What this changes

| Layer | v1 | v2 |
|---|---|---|
| Hook count | 2 | 3 |
| Force-mechanics at hook layer | 0 | 1 (the new PreToolUse) |
| Tier distribution | 1 PASSIVE + 1 INJECT-CONTEXT | 1 PASSIVE + 1 INJECT-CONTEXT + 1 REJECT/WARN |
| Substrate-lock fraction | 0/2 (0%) | 1/3 (33%) |

The 1/3 is at the hook layer only; combined with the existing `approve()` QA gate, CogSig has 2 force-mechanics across the full pipeline (1 at write-time, 1 at promotion-time).

This matches the reframe exactly: **inject continues** (signature still primes context every prompt), **AND act is added** (signature violations get caught at the tool boundary instead of surfacing only in user post-hoc review).

---

## Pattern-as-substrate-lock observation

CogSig's pattern-level mechanisms — `instance_count >= 2` auto-promote threshold, `evidence_list` requirement, `_qa_validate_patterns()` at approve — were ALREADY substrate-lock at construction. They gate state mutation. The cycle-25 audit framing missed crediting them because the audit was scoped to hooks.

This is consistent with the parent-scaffold pattern `pattern-discipline-at-layer-N-not-invocation-at-layer-M`: **discipline at the wrong architectural layer doesn't install**. Text-only rules emit prose; rule-text-with-no-invocation-mechanic stays at the document layer. CogSig's v1 governance was correct AT THE PATTERN-PROMOTION LAYER. The gap was that no analogous force-mechanic existed AT THE TOOL-USE LAYER. v2 closes that gap.

CogSig is therefore a NEW INSTANCE of `pattern-discipline-at-layer-N-not-invocation-at-layer-M` at the CogSig layer. Documenting it here adds one more `n` to the parent scaffold's pattern instance count.

---

## What the docs should say (and now do)

Per the user's "we wanna be injecting AND acting" reframe and the cycle-25 audit's substrate-lock vocabulary, the README + SUBMISSION + audit docs are getting a surgical pass to:

1. Replace overclaim language ("ensures" / "enforces" / "guaranteed") with model-as-decider phrasing ("injects" / "surfaces" / "Claude reads and may follow").
2. Add an "Architecture: Inject + Act" section classifying both v1 (inject-only) and v2 (inject + act) mechanically.
3. Update cite-vs-invoke percentage references with the substrate-lock distinction.
4. Cross-reference the parent-scaffold pattern (`pattern-discipline-at-layer-N-not-invocation-at-layer-M`).

The v1 mechanics (signature inject every prompt, QA gate on approve, governance via Managed Agents in cloud mode) all stay shipped. v2 adds the PreToolUse violation detector as the missing tier-1 force-mechanic.

---

## Cross-references

- **Source audit (parent scaffold):** `~/Flex/Trading/reports/hook_invocation_architecture_audit_2026-04-25.md`
- **Parent pattern:** `pattern-discipline-at-layer-N-not-invocation-at-layer-M` (private scaffold, status:current)
- **CogSig v1 audit:** `AUDIT-2026-04-23.md` (this repo)
- **v2 hook implementation:** parallel dispatch — see commit history for `hooks/pre-tool-use-enforce.sh` + `skills/enforce/SKILL.md` (or similar) when it lands.

---

## v2 status (2026-04-25 — landed in parallel)

The v2 enforcement hook landed via a parallel dispatch concurrent with this honesty refresh:
- `hooks/pre-tool-use-enforce.sh` — `PreToolUse:Edit|Write|MultiEdit` matcher.
- `skills/enforce/SKILL.md` — user-facing documentation for `/cogsig enforce <off|warn|reject>`.

Refer to those artifacts (and the parallel agent's submission report) for the implementation details. This note is the architectural rationale + parent-scaffold pattern cross-reference; the implementation lives in those two files.

## Honest caveat

This note documents an architectural decision. v2 hook code is shipped but until empirically tested (false-positive rates measured against real edits, REJECT-mode tested against signature dimensions of varying confidence), the inject+act framing is "shipped" not "validated". The README + SUBMISSION docs reflect this honestly: v2 is described as added enforcement at the tool-use boundary, not as guaranteed substrate-lock.

Update this note as v2 accumulates measurement data.
