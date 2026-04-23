# Cognitive Signature IDE

**Claude quietly syncs to your cognitive signature — voice (directives, conversational flow, idiomatic tells) + operational patterns (failure modes, reasoning chains, recurring decisions) — and stays aligned as you change.**

A Claude Code plugin that auto-promotes patterns from how you direct AI and from what you've learned through usage. Two functionalities across one pipeline. Three user types. Hands-off by default; user surfaced only on conflict. Built for the **Built with Opus 4.7** hackathon (Cerebral Valley + Anthropic), April 2026.

---

## The problem

You open Claude Code. Every session starts cold. You spend the first 15 minutes bringing Claude up to speed on how you think. Then it forgets. Next session, you do it again. Every polished output is joint-authored — it came from you + Claude iterating — but nothing carries over. Your directing style, your reframes, your trust signals, your idiomatic tells evaporate at the end of every conversation. Worse: the failure modes you hit repeatedly, the reasoning shapes you converge on, the recurring decisions — none of those stack either. Every session, cold.

**The data to fix this is already on your disk.** Claude Code stores every session as a JSONL. Every message you typed is there, tagged `type: user`. We consume that corpus, extract the patterns that are uniquely yours, and feed them back as context so Claude's next response matches how you actually work.

---

## The key insight — contribution, not output

In an LLM-coupled workflow, your **output** is joint-authored. Your code, your prose, your design docs — they emerged from dialogue with Claude. A "signature" extracted from those outputs captures Claude's style as much as yours.

What's **uniquely yours** is what you typed: your directives, your reframes, your hunches, your trust signals, your idiomatic tells. That's the corpus that actually carries your cognitive signature. CogSig extracts from contribution, not from co-output.

(We arrived at this by building the wrong thing first — see *Discovery arc* below. The iteration itself is evidence the architecture reveals its correct target when tested honestly.)

---

## Two functionalities — one pipeline

Your **cognitive signature** has two layers. The plugin captures both.

### Functionality 1 — Voice (directives, conversational flow, insights)

How you talk to AI. Directive style, compression ratio, reframe patterns ("wait but", "hmmmm"), trust signals ("cook it" vs "hold on"), idiomatic tells, iteration cadence, texture energy. Seven dimensions, each with confidence + evidence.

Extracted from raw user-typed directives across your Claude Code session history. No ingestion of polished output — only what you contributed directly. Injected into Claude's response context so suggestions match your tempo and voice.

**Status**: shipped and live-verified. 100% auto-scorer accuracy (see *Measurement*).

### Functionality 2 — Operational patterns (decision templates, failure patterns, tooling invocations, vocabulary anchors)

What you've learned through usage. Captured from the same dialogue corpus as voice, but with a different lens: RECURRING CONTENT patterns rather than stylistic features.

Four dimensions in the shipped schema (v0.2 after adversarial review):

- **recurring_decision_templates** — situation → response mappings. "When facing X, user does Y." Decision shapes the user has converged on through usage.
- **recurring_failure_patterns** — known failure modes the user has encountered and now proactively checks for or flags.
- **recurring_tooling_invocations** — named tools/commands/flags the user invokes repeatedly in specific contexts.
- **vocabulary_anchors** — project-specific terminology, domain vocabulary, recurring named entities. Distinct from voice's idiomatic_tells — this is content-bearing, not stylistic.

Every item requires `instance_count` + `evidence_list` of actual direct quotes. No frequency-enum handwaving; objective defensible counting.

Governance-promoted-only: every pattern passes QA schema validation before entering the permanent signature (deterministic, fast, $0 — refuses malformed items). In `cloud` mode, Brutus (adversarial) and Historian (drift) also run via Managed Agents before promotion. In `team` mode, in-session Brutus/QA/Historian subagents are invokable at the prompt (`@agent-cognitive-signature-ide:<name>`). Hallucinated patterns don't stick.

**Status**: **live-shipped**. `/cogsig init` extracts BOTH voice and operational signatures by default in one command. Same pipeline, different extraction lens on the same corpus. Architecture extends naturally to additional pattern classes (bug patterns as typed sub-class of failure_patterns, reasoning-chain patterns, domain-specific patterns, cross-team patterns) as usage corpus grows.

### The same `capture → extract → govern → inject` pipeline, both layers

```
your Claude Code sessions  →  filter type:user messages  →  Opus 4.7 extracts:
                                 - voice signature (directing domain, 7 dims)
                                 - operational signature (operational domain, 4 dims)
                              governance agents review both  →  signature.json + signature.operational.json  →
                              injected into Claude's response context from this moment on
```

Same pipes, two layers of signal, **both extracted in one command** (`/cogsig init` default). On install, both signatures seed instantly from your existing Claude Code history — alignment from minute one, no warm-up period. Over weeks, both layers refine and deepen: new vocabulary absorbs, operational patterns promote through governance, drift gets caught, the cognitive-scaffolding layer thickens. Claude syncs continuously.

---

## Hands-off by default — exception-triage governance

Default posture: zero touch. The plugin runs quietly in the background. Advisor fires at inflection points automatically; governance agents run automatically **when `active_mode` is `cloud`** (Managed Agents beta); user is surfaced ONLY when something conflicts or needs review.

**What runs silently**:
- Signature extraction on your first `/cogsig init` and on subsequent `/cogsig refresh`
- QA schema validation on every approve/auto-promote (deterministic, no LLM call, $0)
- Governance review (Brutus / QA / Historian via Managed Agents) after every extraction — `active_mode == cloud` only
- Advisor consultation at inflection points (low-confidence extraction, conflicting governance, unexplained drift)
- Injection on every Claude Code response

**What surfaces to you**:
- Signature drift flagged UNEXPLAINED by Historian (pattern shifted with no corpus-source change — worth reviewing)
- Governance conflict (Brutus says WEAK, QA says PASS — advisor reframes, user sees the reframe)
- Significant new patterns promoted (optional — enable via toggle)

The governance layer is the product. Most of the time you don't see it working. When you do, it's because something needs your attention — not noise.

---

## 3 governance tiers × 4 onboarding presets

| User type | Governance infrastructure | Interaction posture |
|-----------|---------------------------|---------------------|
| **Solo / normie** | Standalone — direct API call, inline | Turn on, forget. Advisor fires invisibly. |
| **Power user / team (3-10)** | In-session agents — `brutus` / `qa` / `historian` available at the prompt via `@agent-` mention | Interactive governance available; team signatures exportable |
| **Enterprise** | Cloud-governed — Claude Managed Agents (beta `managed-agents-2026-04-01`) | Compliance + audit + cross-device sync |

Same pipeline. Same tagline. Three governance infrastructures, one choice:

```
/cogsig mode standalone   # default
/cogsig mode team
/cogsig mode cloud
```

Standalone is the default — zero agent setup, instant value. Team and cloud layer on richer governance when users need it.

---

## Onboarding — 3 tiers

**Tier 1 — Auto-seed (default)** — the plugin scans `~/.claude/projects/**/*.jsonl`, filters `type: user` entries, extracts a signature. Works for any Claude Code user with zero extra effort. No file exports. No corpus hunting.

```
/cogsig init
→ Found 100 sessions with ~2,400 directives. Build signature? [Y/n]
→ y
→ extracting...
→ signature active.
```

**Tier 2 — Corpus import** — for users who want a different register (casual chat, Discord, Slack). Point at any JSONL or chat export:

```
/cogsig import-corpus ~/Downloads/discord-export.json --scope personal
```

**Tier 3 — Cold start** — for privacy-focused users. Signature builds from live usage forward. Takes days to stabilize.

```
/cogsig init --no-seed
```

---

## Measurement

Two results. One objective (automated). One architectural (team simulation).

### Auto-scorer: 100% accuracy vs 33% chance — **+66.7pp over chance**

For each of 10 dialogue prompts, Claude generated 3 outputs under 3 conditions (baseline / placebo-signature / real-signature). A separate Claude conversation was given the real signature + the 3 shuffled outputs and asked to predict which was produced under the signature's influence. Result: **10/10 correct**.

The signature carries observable, reproducible features — not a felt-sense phenomenon. A different Claude (no human in the loop) can reliably detect signature effects on output.

### Team simulation: 5 distinct signatures from same pipeline

Four synthetic personas (terse engineer, verbose PM, casual lowercase typer, formal academic) generated via Opus, plus the real user's signature extracted from actual Claude Code history. Same pipeline, 5 visibly distinct signatures — different vocabulary, compression ratio, energy baseline, reframe pattern, capitalization style.

Architecture generalizes across voices cleanly. One pipeline, N users, N distinct signatures.

See `measurement/RESULTS.md` for full data + `measurement/signature-grid.md` for the 5-person side-by-side. Honest caveats included (N=10 small, same model family for generator + judge, synthetic personas labeled clearly).

---

## The demo — what changes with CogSig on

Same prompt, two Claudes:

```
PROMPT TO BOTH: "draft me a quick reply explaining why we're pivoting"

┌─────────── naked Claude ───────────┐   ┌──── Claude + CogSig ────┐
│ Here's a draft reply:               │   │ yo team quick one:       │
│                                     │   │                          │
│ Hi team,                            │   │ pivoting the build —     │
│                                     │   │ OG code-sig assumes user │
│ I wanted to update you on a change  │   │ writes their own code,   │
│ to our build direction. After       │   │ for heavy Claude users   │
│ careful consideration and review    │   │ that breaks. directing-  │
│ of recent feedback, we've decided   │   │ signature captures what  │
│ to pivot our approach.              │   │ the user actually        │
│                                     │   │ contributes — cleaner    │
│ The main drivers are:               │   │ target.                  │
│                                     │   │                          │
│ 1. The original assumption...       │   │ 3 deploy modes stand.    │
│ 2. User feedback indicated...       │   │ full writeup tmr.        │
│ 3. Upon deeper analysis...          │   │                          │
└─────────────────────────────────────┘   └──────────────────────────┘
```

Same information. Radically different shape. The right column matches the user's actual directing style — compressed, lowercase-casual, scaffold-vocab, "tmr" shorthand, parallel-structure thinking.

---

## Governance — the three agents, the one advisor

Signature extraction is subjective. A single Opus call can hallucinate traits, over-generalize from sparse evidence, or drift. Four roles close that gap — and each agent is **dual-function**: it ships for signature governance AND is available as a general-purpose specialist the user can summon for any work.

- **Brutus** — adversarial reviewer (Opus). **Function 1**: "does this signature actually match the samples, or is it inventing traits?" **Function 2**: general-purpose — invoke for code review, design decisions, math/EV claim validation, paper-method stress-test, pre-deploy "what's the worst that could happen." Verdict categories: `KILL / REWORK / PASS-WITH-CAVEATS / PASS`.

- **QA** — quality assurance (Haiku). **Function 1**: schema validation on `signature.json` before inject. **Function 2**: general-purpose — Python compile + import check, dead-code audit, silent-failure detection (bare excepts / swallowed exceptions), schema validation for any JSON, pre-deploy gate audits. Verdict categories: `CLEAN / FIXABLE-IN-30MIN / BLOCKER`.

- **Historian** — drift & evolution tracker (Sonnet). **Function 1**: detects dimension-level drift across signature history (branches on `origin`: `self` vs `imported`). **Function 2**: general-purpose — config drift across sessions, decision diary compaction, metric-trend classification (stable/drifting/oscillating), architecture evolution, retrospectives. Output: `EXPECTED / UNEXPLAINED / NOISE` classification per change + a one-sentence through-line.

- **Advisor** — Anthropic's Claude Advisor pattern (Haiku-executor + Opus-advisor pairing) applied to CogSig. Fires at inflection points: low-confidence extractions, schema soft-fails, conflicting governance reviews, unexplained drift. Returns strategic reframe + suggested action.

### Summoning the agents (general-purpose mode)

At your Claude Code prompt, use the `@agent-<plugin>:<name>` form for unambiguous routing:
```
@agent-cognitive-signature-ide:brutus review this function for silent-failure paths
@agent-cognitive-signature-ide:qa compile-check all 3 files I just edited
@agent-cognitive-signature-ide:historian compare this config to last 5 sessions
```
If no other agents share the short names, `@agent-brutus` / `@agent-qa` / `@agent-historian` also work. Bare prose like "brutus, review this" will sometimes route and sometimes not — the `@agent-` prefix is the guaranteed dispatch.

**Agent function selection is prompt-driven**, not mechanical. The CogSig pipeline issues dispatch prompts that explicitly reference `signature.json` / `samples.json` → the agent uses its Function 1 output format. User-summoned invocations that don't mention signature artifacts → Function 2 output format. No runtime switch; the model reads the invocation context.

**Priority / shadowing caveat.** Claude Code loads agents in this priority order: user-level (`~/.claude/agents/`) > project-level (`.claude/agents/`) > plugin-contributed (lowest). If you already have a `brutus` / `qa` / `historian` agent at a higher level, the plugin version is shadowed. Use the scoped `@agent-cognitive-signature-ide:brutus` form to force-invoke the plugin version.

**The architecture we used to build this plugin is the architecture we ship.** Every fix we applied pre-submission went through the same brutus+qa loop that's now installed on your machine.

### Where the architecture came from

The architecture was derived from problems encountered during extensive Claude Code usage. Every primitive (breadcrumbs / patterns / governance agents / advisor-at-inflection / pattern-promotion thresholds / drift detection / scope-switching / signature export-import) was built in response to a specific failure mode the author hit using Claude. The plugin packages that operational-discipline substrate into a shape any Claude Code user can install.

### Research foundation

The contribution-vs-output insight — that in LLM-coupled workflows, user output is joint-authored and the isolable user signal lives in directives rather than artifacts — wasn't theorized for this hackathon. It was discovered by iterating the plugin and watching signature extraction fail cleanly on code outputs that the author hadn't typed, then on prose outputs that the author had edited-but-not-authored. The pivot from code-signature → writing-signature → directing-signature each happened because the empirical data showed the corpus choice was wrong. The architecture describes its own correct target under honest testing.

The governance + advisor pairing is the operational translation of Anthropic's Claude Advisor pattern (Haiku-executor + Opus-advisor) applied to signature review. The pattern-promotion threshold (`n=2` auto-promote, governance-gated) compresses a multi-session cognitive-scaffolding architecture the author has run as an N=1 research substrate across a long-running project — distilled into a plugin-scale version any Claude Code user can install. The 100% auto-scorer accuracy on the N=10 directing-signature blind test (see *Measurement*) is the empirical validation: signatures extracted from this architecture carry observable, reproducible features detectable without human scoring.

### Live examples of governance catches during this build

Operational patterns — Functionality 2 — catching defects in this plugin during its own construction:

- **Plugin-loader schema violations** (Day 4) — QA dispatched to verify `plugin.json` against Claude Code's actual loader schema; caught 3 critical gaps (manifest at wrong path, `hooks` field format wrong, `skills` array incomplete). Had QA not caught: `claude plugin install .` would have silent-failed during demo recording. All 3 fixed pre-demo.
- **Contaminated blind-test prompts** (Day 4) — Brutus dispatched to stress-test 10 directing-domain prompts before any API calls. Caught "yo" contamination in pivot-reply prompt (baseline would auto-produce yo-register, killing differentiation), two prompts isolating too few signature dimensions. 3 swaps applied; post-swap set covered all 7 dimensions cleanly.
- **Signature factual error** (Day 3, code-domain predecessor) — Signature-Brutus reviewing the first live extraction caught a claim that "PascalCase reserved for constants" when actual constants were UPPER_SNAKE_CASE. Adversarial governance earned its keep on first live run.
- **Advisor self-referential diagnosis** (Day 3) — advisor's first smoke test correctly identified that the manual-class inflection it was firing on matched the verify-first trust mechanic in the signature it was reviewing. Recursive validation landed first-run.
- **Type-assumption gap** (Day 3) — QA caught `summarize_context()` assuming `governance_reviews` was a dict; hardened with isinstance guards. Pre-production hardening before the first real conflict-class inflection.

The governance architecture catches defects in its own construction. The plugin's Functionality 2 claim ("operational patterns capture") is demonstrated by the plugin's own build process catching bugs the build-team would have missed. Governance is the product — visible in pre-demo catches, invisible in default operation.

---

## Discovery arc — why the pivot matters

1. **Started** with code-signature. Shipped end-to-end, first live Opus extraction worked. Managed Agents caught a signature error. Looked good.
2. **Discovered** that for anyone who delegates code generation to Claude, the output captured was Claude's style shaped by user direction — not the user's. A growing segment of Claude Code users don't author their code directly anymore.
3. **Pivoted** to writing-signature. Same structural problem: users in coupled workflows don't direct-author their prose either. The polished output is joint.
4. **Pivoted again** to directing-signature. Raw typed directives are the one corpus that's unambiguously user-authored. Verified against a real 80-directive corpus from live Claude Code sessions — extracted signature carried real user-specific vocabulary, real trust mechanics, real iteration cadence.

The iteration IS part of the product. Both versions live in the commit history as evidence of honest architectural discovery. Meta-level: the architecture revealed its own correct target when tested against real users.

---

## Architecture

```
cognitive-signature-ide/
├── .claude-plugin/
│   └── plugin.json             ← Claude Code plugin manifest
├── skills/
│   ├── init/                   ← /cogsig init — one-command auto-seed
│   ├── capture/                ← scan user's code (legacy code-domain)
│   │   └── dialogue_ingest.py  ← scan JSONL dialogue corpus (directing domain)
│   ├── extract/                ← Opus 4.7 → signature.json (--domain code|directing)
│   ├── inject/                 ← prepend active signature to Claude's context
│   ├── toggle/                 ← /cogsig on|off|status|scope|mode|diff
│   ├── export/                 ← share your signature with a teammate
│   ├── import_sig/             ← load a teammate's signature, origin=imported
│   └── advisor/                ← Claude Advisor pattern at inflection points
├── agents/                     ← in-session governance (team mode)
├── managed-agents/             ← cloud governance (enterprise mode, beta)
├── hooks/
│   ├── hooks.json              ← structured hook registration
│   ├── session-start.sh        ← emit signature status on session start
│   └── post-tool-use.sh        ← (live-signature-update — planned)
├── measurement/
│   ├── blind_test.py           ← 3-condition blind comparison rig
│   ├── score.py                ← user-subjective scoring
│   ├── score_auto.py           ← Claude-as-judge auto-scoring
│   ├── simulate_team.py        ← 5-person team simulation
│   └── RESULTS.md              ← measurement summary
└── signature.json              ← generated, gitignored, user-local
```

---

## The trajectory — quiet sync, expanding scope

- **Day 1** — starter signature from your existing Claude Code history. Claude stops responding in corporate-assistant register.
- **Week 1** — signature refines as you use it. Idiomatic tells, trust signals, reframe patterns get absorbed. Governance catches hallucinated traits before they stick.
- **Month 1+** — operational patterns (Functionality 2) start promoting. Bug patterns, reasoning-chain patterns, recurring decisions graduate from observation into the permanent signature. Claude reasons WITH your accumulated decision patterns, not just your tempo.
- **Month N** — friction near zero. You + Claude operate as a coupled cognitive system producing work neither of you could produce alone.

This doesn't require the full N months to feel valuable — directing-patterns fire on every message and accumulate fast. The plugin's first-install signal is already strong (100% auto-scorer accuracy). The months-long trajectory is what happens after.

---

## Install

```bash
# Prerequisites
export ANTHROPIC_API_KEY=sk-ant-...
pip install anthropic jsonschema

# Clone
git clone https://github.com/Choppaaahh/cognitive-signature-ide
cd cognitive-signature-ide

# One-command onboarding — scans your Claude Code session history + extracts signature
python3 skills/init/init.py --yes

# Check status
python3 skills/toggle/toggle.py status
python3 skills/toggle/toggle.py mode list      # see governance modes
python3 skills/toggle/toggle.py mode cloud     # enterprise

# Inject into Claude's context
python3 skills/inject/inject.py --force
```

Or, once installed as a plugin:

```
/cogsig init
/cogsig status
/cogsig mode cloud
```

---

## License

MIT — see [LICENSE](LICENSE).
