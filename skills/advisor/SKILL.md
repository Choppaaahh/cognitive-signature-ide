---
name: advisor
description: Anthropic Claude Advisor pattern — consulted at executor inflection points (low-confidence extraction, ambiguous dimensions, conflicting governance, unexplained drift) for strategic reframe rather than parameter-tuning.
user-invocable: false
allowed-tools: [Bash, Read]
---

# advisor — strategic reframe at inflection points

Anthropic's Claude Advisor pattern applied to CogSig's pipeline. Executor agents (extract, review, historian) are fast/local/cheap; they do routine work. When they hit an inflection — a moment where tuning-within-frame won't help because the FRAME is wrong — they pause and consult the advisor. Advisor reframes strategically in a short call; executor continues execution in the new frame.

## Inflection classes

| Class | Trigger | Where fired |
|-------|---------|-------------|
| `low-confidence` | any `dimensions[x].confidence < 0.5` after extract | `extract.py` post-extraction |
| `schema-soft-fail` | jsonschema validation surfaces type-coercion / missing-subfield warnings | `extract.py` post-validate |
| `conflicting-governance` | Brutus=WEAK + QA=PASS + Historian=EXPECTED simultaneously | `managed-agents/review.py` post-review |
| `drift-unexplained` | Historian flags >2 dimensions drifted with no corpus-source change | `historian` analysis |

## What advisor DOES

- Reads the full context (signature draft, samples, review outputs, history)
- Identifies whether the executor's PROBLEM FRAMING is wrong, not just whether parameters need tuning
- Returns a short strategic reframe + concrete next action
- Advisor responses are 400-700 tokens (short), so cost is bounded even on Opus

## What advisor does NOT do

- Doesn't retry the extraction itself
- Doesn't modify any files
- Doesn't override governance decisions
- Doesn't block executor — executor decides whether to act on reframe

## Deploy modes — advisor runs across all

- **Standalone** — advisor fires automatically on trigger, user sees reframe output
- **In-session team** — advisor + governance agents both run; advisor consulted when governance agents conflict
- **Cloud (Managed Agents)** — advisor can itself be a Managed Agent (future) or standalone inline (current)

## Scaffold precedent

This pattern is documented in the private scaffold's `pattern-advisor-consult-at-inflection-points` (emerging n=3, 2026-04-20). Three validated instances: temporal-fabrication rule-level fix instead of verbal-discipline; retrieval tournament benchmark reframe; persistent-vs-ephemeral team mode clarification. The pattern maps operationally to Anthropic's Claude Advisor tool (Haiku-executor + Opus-advisor pairing).
