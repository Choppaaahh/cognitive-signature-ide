#!/usr/bin/env bash
# UserPromptSubmit hook — auto-inject cognitive signature on every prompt.
#
# Delivers the core SKILL.md promise ("On every Claude Code prompt if /cogsig on")
# that was un-wired until 2026-04-24. The skill's filesystem invocation path
# existed (inject.py is CLI-runnable); what was missing was the plugin-side
# hook registration that Claude Code fires on each user prompt submission.
#
# Behavior:
#   - Reads stdin JSON from Claude Code (drained to avoid broken pipe)
#   - Locates the user's repo via CLAUDE_PROJECT_DIR
#   - Calls inject.py which:
#       * returns 0 if toggle is OFF (emits off-notice to stderr)
#       * returns 0 if no signature exists (emits capture hint to stderr)
#       * emits signature prefix to stdout when toggle is ON and signature exists
#   - stdout from this hook flows into CC's context before reasoning

set -euo pipefail

# Drain stdin (Claude Code delivers JSON payload we don't need to parse for injection).
cat >/dev/null

REPO="${CLAUDE_PROJECT_DIR:-$(pwd)}"
PLUGIN_ROOT="${CLAUDE_PLUGIN_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
INJECT="$PLUGIN_ROOT/skills/inject/inject.py"
LOG_FILE="${HOME}/.claude/cogsig-enforcement-log.jsonl"
mkdir -p "$(dirname "$LOG_FILE")"
TS="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

if [[ ! -f "$INJECT" ]]; then
    # Hook can still be useful in dev setups without the plugin fully wired;
    # fail soft rather than break user's prompt flow.
    echo "{\"ts\":\"$TS\",\"source\":\"cogsig-user-prompt-submit\",\"trigger\":\"UserPromptSubmit\",\"trust_tier\":\"scripted\",\"result\":\"SKIPPED\",\"reason\":\"inject-script-missing\"}" >> "$LOG_FILE" 2>/dev/null || true
    exit 0
fi

# Call inject — it handles all the "off / no-signature / malformed" cases itself.
# stderr messages ("off" or "no signature found") are suppressed so user-facing
# output only shows on the successful-injection path.
python3 "$INJECT" --repo "$REPO" 2>/dev/null || true

# Audit-trail row (so consumers can count fire frequency vs miss frequency).
echo "{\"ts\":\"$TS\",\"source\":\"cogsig-user-prompt-submit\",\"trigger\":\"UserPromptSubmit\",\"trust_tier\":\"scripted\",\"result\":\"FIRED\",\"reason\":\"inject-attempted\"}" >> "$LOG_FILE" 2>/dev/null || true

exit 0
