# Cognitive Signature IDE

**A Claude Code plugin that captures how YOU think — and injects that signature into Claude's output so it matches your voice instead of a generic one. The architecture is domain-agnostic (code, writing, design). The hackathon demo ships the code domain end-to-end.**

Built for the **Built with Opus 4.7** hackathon (Cerebral Valley + Anthropic), April 2026.

---

## The problem

You open Claude Code. You ask for a helper function. The suggestion is… fine. Syntactically correct. Semantically reasonable. But it doesn't look like *your* code.

You ask it to draft a response. The prose is competent but generic — it doesn't sound like you.

You ask for UI copy. The tone is pleasant, corporate, and indistinguishable from every other LLM output on the internet.

Every time, you rewrite.

Claude has access to your files. It can see how you work. The gap is: **nobody's told Claude to adapt its output to you specifically** — not just your preferences, but your signature. Your cognitive fingerprint. The specific way you structure thought.

## What this is

Four skills, three governance agents, two hooks.

1. **Capture** — sample recent artifacts the user has actually authored, optionally scoped to a subset of the repo (work-code vs personal-code)
2. **Extract** — one Opus 4.7 call produces a structured `signature.json`
3. **Inject** — prepend the active signature to Claude's context so suggestions match the user's voice
4. **Toggle** — `/cogsig on | off | status | scope <name> | export | import | diff` — flip it live, switch between signatures, share signatures across teammates

### Why the architecture matters more than the dimensions

The pipeline — **capture → extract → govern → inject** — is the core loop of any system that learns from observation. Capture what the target produces. Compile it into structured patterns. Govern the patterns with adversarial + validation review. Inject them at decision time.

Most "AI personalization" tools skip the governance step. They capture, they extract, they inject. No review means the signature drifts, hallucinates traits, or overfits to outliers — and nothing notices. The three governance agents close that gap:

- **Signature-Brutus** — adversarial pressure on every extraction: "does this actually match the samples, or is it hallucinating traits?"
- **Signature-QA** — schema validation before signature reaches inject
- **Signature-Historian** — drift detection across sessions, flags unexplained changes

These run as **Claude Managed Agents** (cloud-hosted, `managed-agents-2026-04-01` beta header) — the plugin dogfoods Anthropic's own multi-agent infrastructure on the layer that makes the plugin trustworthy.

### Domain-agnostic by construction

The pipeline is one. The signature schema is a parameter. Swap the schema + extraction prompt, point the capture skill at different file types, and the same pipeline extracts a signature for any creative domain. For the hackathon demo, **code is the end-to-end-shipped domain** — naming convention, comment density, function length, error handling, import organization, structural preference. Writing and design signatures are schema-swaps, not re-architectures. That work lives in **Future Directions** below — intentionally out of scope here so the demo delivers one domain deeply, not three shallowly.

### Per-project signatures

One developer writes different code in different contexts. Work-repo code looks nothing like personal-hobby code — different naming, different error handling, different comment density. A single signature averaged across both is worse than useless; it makes suggestions that match neither.

The capture skill takes an optional `--scope-name` label and `--include` / `--exclude` path filters. The toggle skill tracks which scope is active:

```
/cogsig capture --scope-name work     --include "src/**,lib/**"
/cogsig capture --scope-name personal --include "sandbox/**"
/cogsig extract --scope-name work
/cogsig extract --scope-name personal
/cogsig scope work        → inject uses signature.work.json
/cogsig scope personal    → inject uses signature.personal.json
/cogsig scope list        → all available signatures
```

Scope switching is observable: a `/cogsig status` call shows exactly which signature is active and the samples it came from.

### Sharing signatures across a team

`signature.json` is deliberately not something you commit. It's user-specific, `.gitignore`'d, and personal. But a team that wants consistency — everyone's code matching a shared house style — can export and import signatures without leaking code:

```
/cogsig export --team-id alpha-team     → writes signature.export-alpha-team.json
<teammate>: /cogsig import signature.export-alpha-team.json
```

The imported signature lands with `origin: "imported"` in the JSON. Signature-Historian reads that field and skips drift-analysis automatically, because drift against an imported reference point is expected behavior, not a bug.

### Live-signature-update (the demo moment)

A `PostToolUse` hook watches your edits during the session. As you write code, the active signature JSON updates in real time. The demo video shows the signature mutating as artifacts get produced — a visible, visceral "the plugin is learning you" moment.

### On the lived basis

This capture→extract→govern→inject loop isn't speculative for me. I've been running a version of it on myself as a research environment — events captured as they happen, compiled into patterns, adversarially reviewed, injected at decision time. That lived N=1 is why the governance layer isn't a bolt-on here; it's load-bearing. Subjective extraction without governance compounds errors silently. I've watched it happen and caught it because the review layer was there.

The hackathon claim is the architecture, not the lived version. The lived version is how I know the architecture holds up in practice.

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

## Build steps

- ✅ **Step 1** — repo init, manifest, README, LICENSE, skill + agent scaffolds
- ✅ **Step 2** — capture + extract implementation (code domain end-to-end)
- ⏳ **Step 3** — inject skill + `/cogsig` toggle + diff mode
- ⏳ **Step 4** — Managed Agents governance layer + n=10 blind measurement
- ⏳ **Step 5** — live-signature-update hook + polish + Loom recording
- ⏳ **Step 6** — submission

## Measurement

A pre-submission blind test: 10 prompts, Claude answers each under three conditions — baseline / generic-signature placebo / user's real signature injected. The author picks which output is theirs, no labels visible. Result published in the repo with the submission. This is the Impact-30% grounding — not a theoretical claim, a measurable effect.

## Future directions (out of scope for submission)

- **Writing domain** — sentence length, tonal register, paragraph cadence, idiomatic tells. Schema-swap, same pipeline. Validation is subjective enough to warrant its own post-hackathon iteration.
- **Design domain** — palette preference, spacing density, component composition. Needs a non-code capture layer (Figma API or CSS/HTML sampling). Post-hackathon.

These are architecture-supported but deliberately not shipped for the submission. One domain shipped deeply beats three shipped shallowly.

## License

MIT — see [LICENSE](LICENSE).
