# Cognitive Signature IDE — Submission

**Built with Opus 4.7 · Cerebral Valley + Anthropic · Hackathon window 2026-04-21 → 2026-04-26**

GitHub: https://github.com/Choppaaahh/cognitive-signature-ide
Demo: `demo-video/demo.html` (zero-install, auto-play 2:31 in any browser)

---

## One-line pitch

Claude quietly syncs to your cognitive signature — voice (directives, conversational flow, idiomatic tells) + operational patterns (failure modes, reasoning chains, recurring decisions) — and stays aligned as you change.

---

## The problem

Every Claude Code session starts cold. You spend the first 15 min bringing Claude up to your speed. It forgets. Next session, you do it again. Your directing style, your reframes, your trust signals — joint-authored output carries them implicitly, but nothing carries over between sessions. Failure modes you've hit three times, reasoning shapes you converge on, decisions you keep remaking — none of those stack.

The data to fix this is already on disk. Claude Code stores every session as JSONL; every message you typed is tagged `type: user`. We extract the patterns that are uniquely yours and feed them back as context.

---

## What it does

A Claude Code plugin with **two functionalities on one pipeline**:

1. **Voice signature** — extracts how you direct AI (7 dimensions: directive style, compression, reframe patterns, trust signals, idiomatic tells, iteration cadence, texture). Injected into Claude's response context.

2. **Operational signature** — extracts recurring decision templates, failure patterns, tooling invocations, and vocabulary anchors from multi-turn scaffold work. Auto-promoted to a permanent signature when n≥2 instances observed. User reviews or silent-promotes depending on mode.

**Four onboarding presets** (normie / power / team / enterprise) map to **three deploy modes** (standalone / team-shared / cloud-governed). Normie = silent auto-promote. Power+ = review-first, Claude surfaces pending patterns at session start.

---

## Evidence (measurement/)

- **Auto-scorer**: Claude-as-judge over 10 prompts × 3 conditions (baseline / placebo-signature / real-signature). Result: **10/10 = 100% accuracy vs 33% chance = +66.7pp over chance**. Reproducible via `python3 measurement/score_auto.py`.
- **5-persona team simulation**: 4 synthetic personas (Alice/Bob/Tim/Sue) + real user. Same architecture extracts 5 visibly-distinct signatures. Published as `measurement/signature-grid.md`.
- **Live governance catches during build** (pre-demo): QA caught 3 plugin-loader schema violations before any public action; Brutus caught 3 contaminated blind-test prompts before 30 Opus calls fired; advisor self-referentially diagnosed its own trigger at smoke-test. All cataloged in `README.md` Governance section.

---

## What was built with Claude Opus 4.7

**Everything.** 27+ public commits, ~7,300 lines across 8 skills (init, capture, extract, inject, toggle, import, export, review, advisor), 16 Python files, Remotion + zero-install HTML demo (2 paths), measurement suite, managed-agents integration, hooks, 3 dual-function governance subagents (brutus / qa / historian).

Adversarial review dispatched at every pattern-promotion step during the build: every extraction passed Brutus + QA before shipping. 7 pre-submission error-path fixes applied from final sweep.

## Shipped subagent infra (dual-function)

The 3 governance agents aren't scoped to signature review — they're **dual-function**. Each one serves its signature-governance role AND is available as a general-purpose specialist the user can summon for any work:

- **brutus** (Opus) — adversarial code/decision/math reviewer. `KILL / REWORK / PASS-WITH-CAVEATS / PASS`
- **qa** (Haiku) — schema + compile + dead-code + silent-failure auditor. `CLEAN / FIXABLE-IN-30MIN / BLOCKER`
- **historian** (Sonnet) — drift/change/evolution tracker. `EXPECTED / UNEXPLAINED / NOISE`

Summoned at the Claude Code prompt via `@agent-` mention:
```
@agent-cognitive-signature-ide:brutus review this function
@agent-cognitive-signature-ide:qa compile-check files
@agent-cognitive-signature-ide:historian compare this config to last 5 sessions
```
Function selection is prompt-driven (signature-artifact-naming triggers Function 1; bare user work triggers Function 2). Plugin agents are lowest-priority; scoped `@agent-<plugin>:<name>` form force-invokes when local same-name agents exist. The architecture we used to build this plugin is the architecture we ship.

---

## About the builder

Choppaa — non-technical independent researcher, logistics background. Everything built by and through Claude Code. Disclaimer: this product was **vibecoded**. User purely directed the flow of Opus 4.7 and did nothing technical.

Thank you, team @ Anthropic 🫡
