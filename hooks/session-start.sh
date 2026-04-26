#!/usr/bin/env bash
# SessionStart hook — emit cogsig status on every session start.
#
# Reads stdin JSON from Claude Code (drained but not parsed — status is
# self-contained). Prints a single status line if a signature exists.

set -euo pipefail

cat >/dev/null

REPO="${CLAUDE_PROJECT_DIR:-$(pwd)}"
TOGGLE="$REPO/skills/toggle/toggle.py"
LOG_FILE="${HOME}/.claude/cogsig-enforcement-log.jsonl"
mkdir -p "$(dirname "$LOG_FILE")"
TS="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

if [[ -f "$TOGGLE" ]]; then
    python3 "$TOGGLE" status --repo "$REPO" 2>/dev/null || true
    echo "{\"ts\":\"$TS\",\"source\":\"cogsig-session-start\",\"trigger\":\"SessionStart\",\"trust_tier\":\"scripted\",\"result\":\"FIRED\",\"reason\":\"status-emitted\"}" >> "$LOG_FILE" 2>/dev/null || true
else
    echo "{\"ts\":\"$TS\",\"source\":\"cogsig-session-start\",\"trigger\":\"SessionStart\",\"trust_tier\":\"scripted\",\"result\":\"SKIPPED\",\"reason\":\"toggle-script-missing\"}" >> "$LOG_FILE" 2>/dev/null || true
fi

exit 0
