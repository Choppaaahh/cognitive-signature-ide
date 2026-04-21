#!/usr/bin/env bash
# SessionStart hook — emit cogsig status on every session start.
#
# Reads stdin JSON from Claude Code (drained but not parsed — status is
# self-contained). Prints a single status line if a signature exists.

set -euo pipefail

cat >/dev/null

REPO="${CLAUDE_PROJECT_DIR:-$(pwd)}"
TOGGLE="$REPO/skills/toggle/toggle.py"

if [[ -f "$TOGGLE" ]]; then
    python3 "$TOGGLE" status --repo "$REPO" 2>/dev/null || true
fi

exit 0
