# Cognitive Signature IDE

**Claude quietly syncs to your cognitive signature — voice (directives, conversational flow, idiomatic tells) + operational patterns — and stays aligned as you change.**

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

### Functionality 2 — Operational patterns (failure modes, reasoning chains, recurring decisions)

What you've learned through usage. The architecture is **pattern-agnostic** — anything you can schema + extract + review + inject can be promoted into the permanent signature:

- **Bug patterns** — failure modes your sessions repeatedly hit; after `n=2` repetitions, Claude proactively checks for them before shipping.
- **Reasoning-chain patterns** — how you decompose problems across turns; Claude anticipates the next step rather than waiting for steering.
- **Domain-specific patterns** — accounting vocabulary, engineering rigor, legal precision, customer-support warmth. Multiple scopes per user, each with its own pattern stack. `/cogsig scope <domain>`.
- **Cross-team patterns** — when the same pattern promotes across multiple teammates' imports, it becomes a team-scope pattern; the shared signature captures what the team learned collectively.

Governance-promoted-only: every pattern passes Brutus (adversarial) + QA (schema) + Historian (drift) before entering the permanent signature. Hallucinated patterns don't stick.

**Status**: architecture-supported; directing-signature (Functionality 1) is the first pattern class shipped; bug/reasoning/domain/team classes use the same pipeline as natural extensions with usage.

### The same `capture → extract → govern → inject` pipeline, both layers

```
your Claude Code sessions  →  filter type:user messages  →  Opus 4.7 extracts signature  →
                              governance agents review  →  signature.json  →
                              injected into Claude's response context from this moment on
```

Same pipes, two layers of signal. Over weeks, your signature accrues both — it's not just tone, it's an entire cognitive-scaffolding layer. Claude syncs to that layer continuously.

---

## Hands-off by default — exception-triage governance

Default posture: zero touch. The plugin runs quietly in the background. Advisor fires at inflection points automatically; governance agents run automatically; user is surfaced ONLY when something conflicts or needs review.

**What runs silently**:
- Signature extraction on your first `/cogsig init` and on subsequent `/cogsig refresh`
- Governance review (Brutus / QA / Historian) after every extraction
- Advisor consultation at inflection points (low-confidence extraction, conflicting governance, unexplained drift)
- Injection on every Claude Code response

**What surfaces to you**:
- Signature drift flagged UNEXPLAINED by Historian (pattern shifted with no corpus-source change — worth reviewing)
- Governance conflict (Brutus says WEAK, QA says PASS — advisor reframes, user sees the reframe)
- Significant new patterns promoted (optional — enable via toggle)

The governance layer is the product. Most of the time you don't see it working. When you do, it's because something needs your attention — not noise.

---

## 3 user types × 3 governance deploy modes

| User type | Governance infrastructure | Interaction posture |
|-----------|---------------------------|---------------------|
| **Solo / normie** | Standalone — direct API call, inline | Turn on, forget. Advisor fires invisibly. |
| **Power user / team (3-10)** | In-session agents — Signature-Brutus/QA/Historian spawn via `/team` | Interactive governance available; team signatures exportable |
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

Signature extraction is subjective. A single Opus call can hallucinate traits, over-generalize from sparse evidence, or drift. Four roles close that gap:

- **Signature-Brutus** — adversarial: "does this signature actually match the samples, or is it inventing traits?"
- **Signature-QA** — schema validation before signature reaches inject
- **Signature-Historian** — drift detection across sessions. Branches on `origin` field: `self` gets full drift analysis; `imported` (from `/cogsig import-corpus`) skips drift analysis because cross-user differences are expected.
- **Advisor** — Anthropic's Claude Advisor pattern (Haiku-executor + Opus-advisor pairing) applied to CogSig. Fires at inflection points: low-confidence extractions, schema soft-fails, conflicting governance reviews, unexplained drift. Returns strategic reframe + suggested action.

On first live run of the code-domain version, Signature-Brutus caught a real factual error in the extraction — claimed "PascalCase reserved for constants" when actual constants were UPPER_SNAKE_CASE. Adversarial governance earned its keep on first try. Advisor self-referential diagnosis on first smoke test: correctly identified that manual-class inflection matched the verify-first trust mechanic in the signature it was reviewing. Governance is the product — visible in pre-demo catches, invisible in default operation.

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
