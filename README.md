# Cognitive Signature IDE

A Claude Code plugin that reads how YOU code — naming, comment density, function shape, error handling, structural preferences — and injects that signature into Claude's suggestions so they match your style instead of a generic one.

Built for the **Built with Opus 4.7** hackathon (Cerebral Valley + Anthropic), April 2026.

## The problem

You open Claude Code. You ask for a helper function. The suggestion is… fine. Syntactically correct. Semantically reasonable. But it doesn't look like *your* code. The variable names are wrong. The error handling is over-engineered or under-engineered. The function is twice as long as anything you'd write. You rewrite it.

Every suggestion, you pay that tax.

Claude has access to your codebase. It can see how you code. The gap is: **nobody's told Claude to adapt its output style to you specifically.**

## What this does

Four skills + three governance agents + two hooks.

1. **Capture** — sample recent code you've actually written (`git log --author=you`, recent edits)
2. **Extract** — one Opus 4.7 call analyzes the samples and produces a structured `signature.json` — naming convention, comment density per line, function-length distribution, error-handling posture, import organization, nesting preference
3. **Inject** — prepend the signature to Claude's context so suggestions match your style
4. **Toggle** — `/cogsig on | off | diff` — flip it live, compare mine/theirs/generic side-by-side

### Multi-agent governance (the depth layer)

Signature extraction is subjective. A single Opus call can drift, over-generalize, or pick up noise. Three governance agents review every signature update:

- **Signature-Brutus** — adversarial: "does this signature actually match the samples, or are you hallucinating style traits?"
- **Signature-QA** — schema validation, catches malformed signature JSON before it reaches inject
- **Signature-Historian** — tracks signature drift across sessions, flags unexplained changes

Day 4, these run as **Claude Managed Agents** (cloud-hosted, `managed-agents-2026-04-01` beta header) — the plugin dogfoods Anthropic's own multi-agent infrastructure.

### Live-signature-update (the demo moment)

A `PostToolUse` hook watches your edits during the session. As you type your own code, the signature JSON updates in real time. The demo video shows the signature mutating as code gets written — a visible, visceral "the plugin is learning you" moment.

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
│   ├── capture/             ← sample your recent code
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

- ✅ Day 1 — repo init, manifest, README, LICENSE, skill scaffolds
- ⏳ Day 2 — capture + extract end-to-end
- ⏳ Day 3 — inject + /cogsig toggle + diff mode
- ⏳ Day 4 — Managed Agents governance
- ⏳ Day 5 — live-signature-update hook + polish + Loom recording
- ⏳ Day 6 — submit by Sunday Apr 26, 8 PM EDT

## Why this matters

The current default is Claude adapting you to its style. This flips it: Claude adapts to yours. The signature extraction generalizes beyond code — the same architecture applies to writing tone, design language, and any other domain where "match the user's voice" beats "match the generic pattern."

## License

MIT — see [LICENSE](LICENSE).
