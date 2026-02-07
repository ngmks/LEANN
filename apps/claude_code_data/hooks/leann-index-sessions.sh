#!/bin/bash
# leann-index-sessions.sh — SessionStart hook for LEANN session indexing.
# Installed by /index-sessions skill.
#
# Runs an incremental (or initial) index update for the current project's
# Claude Code sessions. Excludes the current session (just started, empty).
#
# Synchronous: blocks session start for ~2-3s. Errors are visible in
# verbose mode (Ctrl+O). Stdout is suppressed to avoid polluting Claude's
# context (SessionStart stdout is injected into context).

set -euo pipefail

# --- Resolve LEANN repo from the `leann` CLI symlink ---
LEANN_BIN=$(readlink -f "$(which leann)" 2>/dev/null) || {
    echo "leann CLI not found on PATH" >&2
    exit 1
}
# leann binary is at <repo>/.venv/bin/leann
LEANN_REPO=$(dirname "$(dirname "$(dirname "$LEANN_BIN")")")

if [ ! -f "$LEANN_REPO/apps/claude_code_rag.py" ]; then
    echo "apps/claude_code_rag.py not found in $LEANN_REPO" >&2
    exit 1
fi

# --- Parse JSON input from stdin ---
INPUT=$(cat)
SESSION_ID=$(echo "$INPUT" | jq -r '.session_id // empty')
CWD=$(echo "$INPUT" | jq -r '.cwd // empty')

if [ -z "$CWD" ]; then
    echo "No cwd in hook input" >&2
    exit 1
fi

PROJECT_NAME=$(basename "$CWD")

# --- Run incremental index update ---
OUTPUT=$(cd "$LEANN_REPO" && uv run python -m apps.claude_code_rag \
    --project-filter "$PROJECT_NAME" \
    --exclude-session "$SESSION_ID" 2>&1)
STATUS=$?

if [ $STATUS -ne 0 ]; then
    echo "LEANN index update failed for project '$PROJECT_NAME':" >&2
    echo "$OUTPUT" >&2
    exit 1
fi

# Success: suppress stdout (SessionStart stdout goes to Claude's context)
exit 0
