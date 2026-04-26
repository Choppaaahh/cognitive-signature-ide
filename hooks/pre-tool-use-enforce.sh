#!/usr/bin/env bash
# PreToolUse hook — CogSig v2 enforcement layer.
#
# Fires on Edit | Write | MultiEdit BEFORE the tool executes. Reads the proposed
# file content from the tool input, compares against the active signature.json,
# and enforces per the user-selected mode (off / warn / reject).
#
# Hook contract (Claude Code):
#   - stdin: JSON payload with tool_name + tool_input + cwd
#   - stdout: advisory text (only emitted in WARN mode and when violations exist)
#   - exit 0: pass (or warn-with-pass)
#   - exit 1: REJECT (only fires in mode=reject AND severity=high)
#
# Mode determination (in priority order):
#   1. signature.json field `enforcement_mode` (off | warn | reject)
#   2. .signature-cache/state.json field `enforcement_mode`
#   3. default = 'warn' (low-FP-risk start)
#
# FP mitigation:
#   - whitelist patterns from signature.enforcement_whitelist bypass the hook
#   - per-turn pause via .signature-cache/enforcement_pause flag (auto-clears on next prompt)
#   - graceful degrade: missing/unreadable signature → exit 0 silently
#   - log every check to ~/.claude/cogsig-enforcement-log.jsonl with provenance trio

set -uo pipefail

# Locate the user's repo + the plugin root
REPO="${CLAUDE_PROJECT_DIR:-$(pwd)}"
PLUGIN_ROOT="${CLAUDE_PLUGIN_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
DETECTOR="$PLUGIN_ROOT/scripts/check_signature_violations.py"
LOG_FILE="${HOME}/.claude/cogsig-enforcement-log.jsonl"

mkdir -p "$(dirname "$LOG_FILE")"

# Read stdin payload (JSON from Claude Code)
PAYLOAD="$(cat 2>/dev/null || true)"
if [[ -z "$PAYLOAD" ]]; then
    exit 0  # nothing to check; pass
fi

# Required tools (graceful degrade if missing)
if ! command -v jq >/dev/null 2>&1 || ! command -v python3 >/dev/null 2>&1; then
    exit 0
fi
if [[ ! -f "$DETECTOR" ]]; then
    exit 0  # detector missing (dev install); pass silently
fi

# Extract tool_name + target file path + proposed content
TOOL_NAME="$(echo "$PAYLOAD" | jq -r '.tool_name // ""')"
case "$TOOL_NAME" in
    Edit|Write|MultiEdit) ;;
    *) exit 0 ;;  # not our concern
esac

# File path lives in different fields depending on tool
FILE_PATH="$(echo "$PAYLOAD" | jq -r '.tool_input.file_path // ""')"

# Extract proposed content per tool shape
case "$TOOL_NAME" in
    Write)
        PROPOSED_CONTENT="$(echo "$PAYLOAD" | jq -r '.tool_input.content // ""')"
        ;;
    Edit)
        PROPOSED_CONTENT="$(echo "$PAYLOAD" | jq -r '.tool_input.new_string // ""')"
        ;;
    MultiEdit)
        # Concatenate all new_strings
        PROPOSED_CONTENT="$(echo "$PAYLOAD" | jq -r '[.tool_input.edits[]?.new_string] | join("\n")')"
        ;;
esac

if [[ -z "$PROPOSED_CONTENT" ]]; then
    exit 0
fi

# Locate active signature: read state.json for active_scope
STATE_FILE="$REPO/.signature-cache/state.json"
ACTIVE_SCOPE="default"
PAUSE_FLAG="$REPO/.signature-cache/enforcement_pause"
if [[ -f "$STATE_FILE" ]]; then
    ACTIVE_SCOPE="$(jq -r '.active_scope // "default"' "$STATE_FILE" 2>/dev/null || echo default)"
fi

# Per-turn pause: atomic flag consumption (mv is atomic on POSIX — succeeds
# for exactly ONE process if multiple hook invocations race on the same flag).
if [[ -f "$PAUSE_FLAG" ]]; then
    if mv "$PAUSE_FLAG" "$PAUSE_FLAG.consumed.$$" 2>/dev/null; then
        rm -f "$PAUSE_FLAG.consumed.$$"
        TS_PAUSE="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
        echo "{\"ts\":\"$TS_PAUSE\",\"source\":\"cogsig-pre-tool-use-enforce\",\"trigger\":\"PreToolUse:$TOOL_NAME\",\"trust_tier\":\"scripted\",\"file\":\"$FILE_PATH\",\"result\":\"PAUSED\",\"reason\":\"override-flag\"}" >> "$LOG_FILE" 2>/dev/null || true
        exit 0
    fi
    # mv failed (lost the race) — fall through to normal enforcement
fi

if [[ "$ACTIVE_SCOPE" == "default" ]]; then
    SIG_FILE="$REPO/signature.json"
else
    SIG_FILE="$REPO/signature.${ACTIVE_SCOPE}.json"
fi

if [[ ! -f "$SIG_FILE" ]]; then
    exit 0  # no signature; nothing to enforce against
fi

# Determine enforcement mode (signature > state > default)
MODE="$(jq -r '.enforcement_mode // empty' "$SIG_FILE" 2>/dev/null)"
if [[ -z "$MODE" && -f "$STATE_FILE" ]]; then
    MODE="$(jq -r '.enforcement_mode // empty' "$STATE_FILE" 2>/dev/null)"
fi
MODE="${MODE:-warn}"

if [[ "$MODE" == "off" ]]; then
    exit 0
fi

# Check whitelist patterns
WHITELIST_HIT=0
WL_PATTERNS="$(jq -r '.enforcement_whitelist[]? // empty' "$SIG_FILE" 2>/dev/null)"
if [[ -n "$WL_PATTERNS" && -n "$FILE_PATH" ]]; then
    while IFS= read -r pattern; do
        [[ -z "$pattern" ]] && continue
        if [[ "$FILE_PATH" == *"$pattern"* ]]; then
            WHITELIST_HIT=1
            break
        fi
    done <<< "$WL_PATTERNS"
fi
if [[ "$WHITELIST_HIT" == "1" ]]; then
    TS_WL="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    echo "{\"ts\":\"$TS_WL\",\"source\":\"cogsig-pre-tool-use-enforce\",\"trigger\":\"PreToolUse:$TOOL_NAME\",\"trust_tier\":\"scripted\",\"file\":\"$FILE_PATH\",\"result\":\"WHITELISTED\",\"reason\":\"file-path-whitelist\"}" >> "$LOG_FILE" 2>/dev/null || true
    exit 0
fi

# Run the detector
VERDICT_JSON="$(printf '%s' "$PROPOSED_CONTENT" | python3 "$DETECTOR" \
    --signature "$SIG_FILE" \
    --filename "$FILE_PATH" 2>/dev/null || echo '{"severity":"none","recommended_action":"PASS","violations":[]}')"

SEVERITY="$(echo "$VERDICT_JSON" | jq -r '.severity // "none"')"
RECOMMENDED="$(echo "$VERDICT_JSON" | jq -r '.recommended_action // "PASS"')"
VIOL_COUNT="$(echo "$VERDICT_JSON" | jq -r '.violations | length')"

# Log every check (provenance trio: source / trigger / trust_tier)
TS="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
LOG_ROW="$(jq -nc \
    --arg ts "$TS" \
    --arg source "cogsig-pre-tool-use-enforce" \
    --arg trigger "PreToolUse:$TOOL_NAME" \
    --arg trust_tier "scripted" \
    --arg file "$FILE_PATH" \
    --arg mode "$MODE" \
    --arg sev "$SEVERITY" \
    --arg rec "$RECOMMENDED" \
    --argjson nviol "$VIOL_COUNT" \
    --argjson verdict "$VERDICT_JSON" \
    '{ts:$ts, source:$source, trigger:$trigger, trust_tier:$trust_tier, file:$file, mode:$mode, severity:$sev, recommended:$rec, violations:$nviol, verdict:$verdict}'
)"
echo "$LOG_ROW" >> "$LOG_FILE" 2>/dev/null || true

# Decide
if [[ "$SEVERITY" == "none" ]]; then
    exit 0
fi

# Build advisory text (used by warn or reject)
ADVISORY="$(echo "$VERDICT_JSON" | jq -r '
    "[CogSig advisory — " + .severity + " severity, recommended " + .recommended_action + "]\n" +
    (.violations | map("  - " + .rule + " (" + .severity + "): " + .evidence) | join("\n")) +
    "\n  (signature: " + (.domain // "?") + ", file: " + (.filename // "?") + ")\n" +
    "  to bypass once: touch .signature-cache/enforcement_pause then retry\n" +
    "  to disable: /cogsig toggle-enforce off"
')"

case "$MODE" in
    warn)
        # stdout flows to user as advisory; exit 0 = pass
        echo "$ADVISORY"
        exit 0
        ;;
    reject)
        if [[ "$SEVERITY" == "high" ]]; then
            # stderr + exit 1 = block the tool call
            echo "$ADVISORY" >&2
            exit 1
        else
            # medium/low under reject mode degrade to warn
            echo "$ADVISORY"
            exit 0
        fi
        ;;
    *)
        exit 0
        ;;
esac
