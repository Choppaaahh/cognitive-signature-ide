# managed-agents/

Cloud-hosted governance agents for signature extraction review — implemented on
Claude Managed Agents (public beta, header `managed-agents-2026-04-01`).

## Why cloud-hosted

- **Independent review** — governance agents don't share the user's working-context bias
- **Persistent history** — Signature-Historian can track drift across machines
- **Dogfood signal** — the plugin exercises Anthropic's own multi-agent infrastructure on the layer that most benefits from it

## What's here

- **client.py** — shared helpers: agent/environment bootstrap, signature + samples + history loaders, ID caching
- **review.py** — run the three governance agents on the active signature, stream their responses back, write to `.signature-cache/reviews/<ts>.json`

## The three governance agents

All three are created on first run and their IDs cached in `.signature-cache/managed-agents.json`. System prompts live in `client.py::GOVERNANCE_AGENTS`.

| Agent | Model | Role |
|-------|-------|------|
| Signature-Brutus | `claude-opus-4-7` | Adversarial review of every dimension vs source samples |
| Signature-QA | `claude-haiku-4-5-20251001` | Schema validation, PASS/FAIL |
| Signature-Historian | `claude-sonnet-4-6` | Drift classification across history (respects `origin: imported` branch) |

## Usage

```bash
export ANTHROPIC_API_KEY=sk-ant-...

# First run — creates environment + 3 agents, caches IDs
python3 managed-agents/review.py

# Subsequent runs — reuses cached IDs
python3 managed-agents/review.py

# Specific scope (per-project signatures)
python3 managed-agents/review.py --scope-name work

# Force-recreate agents (schema change, prompt change, etc)
python3 managed-agents/review.py --force-recreate
```

## Output

Reviews are written to `.signature-cache/reviews/review-<scope>-<timestamp>.json` with:

```json
{
  "run_ts": "ISO",
  "scope": "default",
  "signature_version": "0.1",
  "signature_generated_ts": "...",
  "origin": "self",
  "reviews": {
    "signature-brutus":    {"session_id": "...", "tool_uses": [...], "response": "..."},
    "signature-qa":        {"session_id": "...", "tool_uses": [...], "response": "..."},
    "signature-historian": {"session_id": "...", "tool_uses": [...], "response": "..."}
  }
}
```

The summary is also printed to stdout for interactive runs.

## Pricing

Claude Managed Agents charges $0.08/session-hour plus standard token costs. Each governance run spins up three short-lived sessions — typical per-review cost is under a few cents for the session-time, plus tokens for the prompts + responses.

## What this does NOT do

- Does not modify any files in your repo — read-only analysis
- Does not gate `extract` or `inject` — reviews are advisory, not enforcing
- Does not upload your source code anywhere except to the governance agents you created (they see `samples.json` contents as part of Brutus's review prompt — samples stay inside your account)
