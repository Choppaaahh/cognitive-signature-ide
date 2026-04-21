# managed-agents/

Cloud-hosted governance agents for signature extraction review.

## Target (Step 4)

The three governance agents defined in `../agents/` (Signature-Brutus, Signature-QA, Signature-Historian) run locally as Claude Code sub-agents. Step 4 migrates them to **Claude Managed Agents** (beta: `managed-agents-2026-04-01` header) so governance runs cloud-side, independent of the user's session.

## Why cloud-hosted

- **Independent review** — governance agents don't share the user's working-context bias
- **Persistent history** — Signature-Historian can track drift across machines
- **Dogfood signal** — the plugin exercises Anthropic's multi-agent infrastructure on the layer that most benefits from it

## Files to land at Step 4

- `signature-brutus.yaml` — Managed Agent definition (translated from `../agents/signature-brutus.md`)
- `signature-qa.yaml` — Managed Agent definition
- `signature-historian.yaml` — Managed Agent definition
- `client.py` — wrapper calling Managed Agents via the beta API header

## Not yet implemented

This directory is a placeholder. The `../agents/*.md` files are the current source-of-truth governance definitions and run as Claude Code sub-agents. Step 4 work translates them to the Managed Agents format and wires the cloud calls.
