# Cognitive Signature IDE

**A Claude Code plugin that captures how YOU think — across code, writing, design, any creative domain — and injects that signature into Claude's output so it matches your voice instead of a generic one.**

Built for the **Built with Opus 4.7** hackathon (Cerebral Valley + Anthropic), April 2026.

---

## The problem

You open Claude Code. You ask for a helper function. The suggestion is… fine. Syntactically correct. Semantically reasonable. But it doesn't look like *your* code.

You ask it to draft a response. The prose is competent but generic — it doesn't sound like you.

You ask for UI copy. The tone is pleasant, corporate, and indistinguishable from every other LLM output on the internet.

Every time, you rewrite.

Claude has access to your files. It can see how you work. The gap is: **nobody's told Claude to adapt its output to you specifically** — not just your preferences, but your signature. Your cognitive fingerprint. The specific way you structure thought.

## What this is

A **general-purpose signature extractor** that points at any domain you create in. Four skills, three governance agents, two hooks — domain-agnostic by design.

1. **Capture** — sample recent artifacts the user has actually authored (code, prose, docs, configs, design specs, anything text-form)
2. **Extract** — one Opus 4.7 call analyzes the samples and produces a structured `signature.json` for that domain
3. **Inject** — prepend the signature to Claude's context so suggestions match the user's signature in that domain
4. **Toggle** — `/cogsig on | off | diff` — flip it live, compare mine/theirs/generic side-by-side

### Domains (same architecture, different dimensions)

The core pipeline is one; the output schema adapts per domain.

| Domain | Signature dimensions |
|--------|---------------------|
| **Code** (Day 2–3 primary demo) | naming convention · comment density · function length · error handling · import organization · structural preference |
| **Writing** (stretch) | sentence length distribution · vocabulary register · tonal temperature · paragraph cadence · idiomatic tells · punctuation habits |
| **Design** (stretch) | palette preference · spacing density · component composition · motion preference · typographic rhythm |
| **Any** | plug in your dimension schema, the skill pipeline stays unchanged |

Code is the first-implemented instance because it's testable, objective, and demoable in 3 minutes. The architecture is domain-agnostic — swap the extraction prompt and schema, point it at any creative output.

### Multi-agent governance (the depth layer)

Signature extraction is subjective. A single Opus call can drift, over-generalize, or pick up noise. Three governance agents review every signature update:

- **Signature-Brutus** — adversarial: "does this signature actually match the samples, or are you hallucinating traits?"
- **Signature-QA** — schema validation, catches malformed signature JSON before it reaches inject
- **Signature-Historian** — tracks signature drift across sessions, flags unexplained changes

On Day 4, these run as **Claude Managed Agents** (cloud-hosted, `managed-agents-2026-04-01` beta header) — the plugin dogfoods Anthropic's own multi-agent infrastructure.

### Live-signature-update (the demo moment)

A `PostToolUse` hook watches your edits during the session. As you type your own code (or write, or design), the signature JSON updates in real time. The demo video shows the signature mutating as artifacts get produced — a visible, visceral "the plugin is learning you" moment.

## Why this is more than a style matcher

The capture → extract → govern → inject pipeline is a **compressed cognitive scaffold**. Same primitives I use in my own long-running research environment — just carved out for one specific use case and put on an IDE rail.

| General scaffold | Cognitive Signature IDE |
|------------------|------------------------|
| observe events (logs, breadcrumbs) | capture (observe artifacts) |
| compile events into patterns | extract (Opus 4.7 → signature.json) |
| promoted patterns | signature.json |
| adversarial + QA + history agents | Signature-Brutus / QA / Historian |
| inject patterns at session start | inject skill → context prefix |
| reasoning-chain log | signature_history.jsonl |

In other words: this plugin is a thinking-architecture distilled for IDE use. Point it at code → it matches your code. Point it at your Notion → it matches your writing. Point it at your Figma → it matches your design.

The generic vector is the problem. The signature vector is the fix. And it's the same architecture end to end.

## Installation

*(Day 5 — install instructions land after the plugin is feature-complete.)*

```bash
# placeholder
claude plugin install cognitive-signature-ide
```

## Architecture

```
cognitive-signature-ide/
├── plugin.json              ← Claude Code plugin manifest
├── skills/
│   ├── capture/             ← sample user artifacts (code/prose/design)
│   ├── extract/             ← Opus 4.7 → signature.json
│   ├── inject/              ← prepend signature to context
│   └── toggle/              ← /cogsig slash command
├── hooks/
│   ├── post-tool-use.sh     ← live-signature-update
│   └── session-start.sh     ← load cached signature
├── agents/                  ← local governance agent definitions
├── managed-agents/          ← cloud-hosted governance (Day 4)
└── signature.json           ← generated, user-specific, .gitignored
```

## Status (live)

- ✅ Day 1 — repo init, manifest, README, LICENSE, skill + agent scaffolds
- ⏳ Day 2 — capture + extract end-to-end on CODE domain
- ⏳ Day 3 — inject + /cogsig toggle + diff mode
- ⏳ Day 4 — Managed Agents governance layer
- ⏳ Day 5 — live-signature-update hook + multi-domain demo (writing + design) + polish
- ⏳ Day 6 — submit by Sunday Apr 26, 8 PM EDT

## License

MIT — see [LICENSE](LICENSE).
