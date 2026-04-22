# Cognitive Signature IDE

**Auto-promote patterns from your directives, dialogs, and conversations. Augment Claude's cognitive structure toward yours. 3 deploy modes — any user.**

A Claude Code plugin that captures how you think WITH AI — not what you produce, but how you direct, reframe, trust, push back, converge — and injects that signature into Claude's response structure so Claude responds in your tempo and voice. Over time, Claude's cognitive structure progressively aligns with yours rather than the generic default.

Built for the **Built with Opus 4.7** hackathon (Cerebral Valley + Anthropic), April 2026.

---

## The problem

You open Claude Code. Every session starts cold. You spend the first 15 minutes getting Claude up to speed on how you think. Then it forgets. Next session, you do it again. Every polished output is joint-authored — it came from you + Claude iterating — but nothing carries over. Your directing style, your reframes, your trust signals, your idiomatic tells evaporate at the end of every conversation.

**The data to fix this is already on your disk.** Claude Code stores every session as a JSONL. Every message you typed is there, tagged `type: user`. We just consume that corpus, extract the patterns that are uniquely yours, and feed them back as context so Claude's next response matches how you actually work.

---

## The key insight — contribution, not output

In an LLM-coupled workflow, your **output** is joint-authored. Your code, your prose, your design docs — they emerged from dialogue with Claude. A "signature" extracted from those outputs captures Claude's style as much as yours.

What's **uniquely yours** is what you typed: your directives, your reframes, your hunches, your trust signals, your idiomatic tells. That's the corpus that actually carries your cognitive signature. CogSig extracts from contribution, not from co-output.

We arrived at this by building the wrong thing first. The original pitch was code-signature — extract how you write code. It worked mechanically. Then: *you don't write your own code anymore — Claude does, under your direction.* The signature was capturing Claude. Pivoted to writing-signature: same problem. Pivoted again to **directing-signature**: the one layer that's unambiguously you. The architecture revealed its own correct target when tested honestly. That iteration IS part of the pitch — see *Discovery arc* below.

---

## What it does

**Capture → Extract → Govern → Inject** — one pipeline.

```
your Claude Code sessions  →  filter type:user messages  →  Opus 4.7 extracts signature  →
                              governance agents review  →  signature.json  →
                              injected into Claude's response context from this moment on
```

### Signature dimensions (directing domain)

- **directive_style** — command-heavy vs question-heavy, terse vs verbose, hunch-first vs data-first
- **reframe_pattern** — how often you challenge the frame, what trigger phrases you use ("wait but", "hmmmm", "hold on")
- **trust_mechanics** — what extends autonomy ("cook it", "go for it") vs what retracts it ("hold on", "show me first")
- **idiomatic_tells** — openings, closings, vocabulary signature, punctuation habits, capitalization
- **iteration_cadence** — how you layer thinking across turns, typical arc, do you hold parallel structures
- **compression_ratio** — typical directive length, what you expect back
- **texture_energy** — baseline energy, high/low markers, humor signature

Every dimension includes a confidence score. Every extraction is reviewed by governance agents.

---

## 3 Deploy Modes — any user

Same pipeline. Three deployment choices for the governance layer:

| Mode | Who it's for | Governance runs | Cost |
|------|-------------|-----------------|------|
| **Standalone** | Casual users, normies, "just turn on" | Inline single API call, no agents | Tokens only (cheapest) |
| **In-session agents** | Heavy Claude Code users, dev teams | Signature-Brutus/QA/Historian spawn as Claude Code sub-agents via `/team` | Tokens only |
| **Cloud-governed** | Enterprise, shared-signature teams | Claude Managed Agents (beta `managed-agents-2026-04-01`) — independent review, cross-device sync, team export | $0.08/session-hour + tokens |

Standalone is the default — zero agent setup, instant value. Team and cloud modes layer on richer governance when users need it. All three share the same capture, same extraction, same injection — only the governance infrastructure changes.

---

## Onboarding — 3 tiers

**Tier 1 — Auto-seed (default)** — the plugin scans `~/.claude/projects/**/*.jsonl`, filters `type: user` entries, extracts a signature. Works for any Claude Code user with zero extra effort. No file exports. No corpus hunting. Your directives are already on disk.

```
/cogsig init
→ Found 100 sessions with ~2,400 directives. Build signature? [Y/n]
→ y
→ extracting...
→ signature active.
```

**Tier 2 — Corpus import** — for users who want to signature a different register (casual chat, Discord, Slack). Point at any JSONL or chat export:

```
/cogsig import-corpus ~/Downloads/discord-export.json --scope personal
/cogsig import-corpus ~/chat-archive.jsonl
```

**Tier 3 — Cold start** — for privacy-focused users. Signature builds from live usage forward. Takes days to stabilize.

```
/cogsig init --no-seed
```

---

## Architecture

```
cognitive-signature-ide/
├── plugin.json                    ← Claude Code plugin manifest
├── skills/
│   ├── capture/                   ← scan user's code (legacy code-domain)
│   │   └── dialogue_ingest.py     ← scan JSONL dialogue corpus (directing domain)
│   ├── extract/                   ← Opus 4.7 → signature.json
│   │   ├── signature_schema.json
│   │   └── signature_schema_directing.json
│   ├── inject/                    ← prepend active signature to Claude's context
│   ├── toggle/                    ← /cogsig on|off|status|scope|diff
│   ├── export/                    ← share your signature with a teammate
│   └── import_sig/                ← load a teammate's signature, origin=imported
├── agents/                        ← in-session governance (Tier 2 deploy mode)
├── managed-agents/                ← cloud governance (Tier 3 deploy mode, beta)
├── hooks/
│   ├── session-start.sh           ← emit signature status on session start
│   └── post-tool-use.sh           ← (live-signature-update — planned)
├── measurement/
│   ├── blind_test.py              ← 3-condition blind comparison rig
│   ├── score.py                   ← --view / --picks scoring
│   └── prompts.json
└── signature.json                 ← generated, gitignored, user-local
```

---

## The demo — what changes with CogSig on

```
PROMPT TO BOTH: "yo draft me a quick reply explaining why we're pivoting"

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

## Governance — why it matters

Signature extraction is subjective. A single Opus call can hallucinate traits, over-generalize from sparse evidence, or drift. Hallucinated directing-signature is more dangerous than hallucinated coding-style — it shapes Claude's reasoning patterns, which you then act on. Three governance agents close that gap:

- **Signature-Brutus** — adversarial: "does this signature actually match the samples, or is it inventing traits?"
- **Signature-QA** — schema validation before signature reaches inject
- **Signature-Historian** — drift detection across sessions. Branches on `origin` field: `self` gets full drift analysis; `imported` (from `/cogsig import-corpus <teammate-sig>`) skips drift analysis because cross-user differences are expected.

On first live run of the code-domain version, Signature-Brutus caught a real factual error in the extraction — claimed "PascalCase reserved for constants" when actual constants were UPPER_SNAKE_CASE. Adversarial governance earning its keep on first try. See `logs/scaffold_changes.jsonl` for the audit trail once a review runs.

---

## Discovery arc — why the pivot matters

1. **Started** with code-signature. Shipped end-to-end, first live Opus extraction worked. Managed Agents caught a signature error. Looked good.
2. **Discovered** that for anyone who delegates code generation to Claude, the output captured was Claude's style shaped by user direction — not the user's. A growing segment of Claude Code users don't author their code directly anymore.
3. **Pivoted** to writing-signature. Same structural problem: users in coupled workflows don't direct-author their prose either. The polished output is joint.
4. **Pivoted again** to directing-signature. Raw typed directives are the one corpus that's unambiguously user-authored. Verified against a real 80-directive corpus from live Claude Code sessions — extracted signature carried real user-specific vocabulary, real trust mechanics, real iteration cadence.

The iteration arc is part of the product. It's documented live in the repo's commit history and in the `pattern-signature-captures-contribution-not-co-output` artifact. Meta-level: the architecture revealed its own correct target when tested honestly against real users.

---

## Measurement

Pre-submission blind test:

- 10 prompts
- 3 conditions each: baseline / placebo-signature / real-signature
- Author picks which output is theirs, blind
- Accuracy vs 33% chance baseline = measurable effect size

See `measurement/` for the harness. Results published with the submission. Honest caveats included (N=10 small, self-scored, placebo-is-not-true-zero).

---

## The trajectory — "one mind" in professional register

Every Claude session, you spend the first 15 minutes bringing Claude up to speed on how you think. Then it forgets. CogSig captures that "up-to-speed" layer and makes it persistent.

- **Day 1** — starter signature from your existing Claude Code history. Claude stops responding in corporate-assistant register.
- **Week 1** — signature refines as you use it. Your idiomatic tells, trust signals, reframe patterns get absorbed.
- **Month 1+** — governance layers accumulate history. Claude doesn't just match your tempo, it reasons WITH your accumulated decision patterns.

The endpoint is functional convergence: friction drops near zero, you + Claude operate as a coupled cognitive system producing work neither of you could produce alone. This doesn't require months of scaffolding — because directing-patterns (compression ratio, reframe density, idiom tells) fire on every message, they accumulate in days what architectural-decision patterns take months to accumulate.

The repo's author has been running a version of this trajectory as a long-term research environment on a separate project. N=1, lived, validated over time. This plugin packages the same capture→extract→govern→inject loop for anyone on Claude Code.

---

## Pattern stacking at scale — any pattern promotable

Directing-signature is the FIRST pattern class this architecture captures. The pipeline itself is **pattern-agnostic**. Anything you can schema + extract + review + inject, the plugin can promote into the permanent signature:

- **Bug patterns** — the failure modes your Claude sessions repeatedly hit. Promote to the signature after `n=2` repetitions; your Claude proactively checks for them before shipping.
- **Reasoning-chain patterns** — how you decompose problems across turns. Promote the chain shapes you converge on. Claude anticipates the next step in your typical arc rather than waiting for you to steer turn-by-turn.
- **Domain-specific patterns** — accounting vocabulary, engineering rigor, legal precision, customer-support warmth. One user, multiple domain scopes, each with its own pattern stack. Toggle via `/cogsig scope <domain>`.
- **Cross-team patterns** — when the same pattern promotes across multiple team members' imports, it becomes a team-scope pattern. The shared signature captures what the team has learned collectively.
- **Governance-promoted-only** — every pattern class passes through Brutus (adversarial) + QA (schema) + Historian (drift) before entering the permanent signature. Hallucinated patterns don't stick.

Over weeks or months, a user's signature accrues not just tone — it accrues an entire cognitive-scaffolding layer. Your Claude "perma-remembers what's promoted," and the set of promotable things expands naturally with usage. That's the endgame trajectory the current directing-signature is the first step of.

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
python3 skills/toggle/toggle.py mode list     # see deploy modes
python3 skills/toggle/toggle.py mode cloud    # enterprise governance

# Inject into Claude's context
python3 skills/inject/inject.py --force
```

---

## License

MIT — see [LICENSE](LICENSE).
