#!/bin/bash
# setup-leann-sessions.sh — One-shot setup for LEANN session indexation.
# Called by /index-sessions skill.
#
# Does:
#   1. Check prerequisites (leann, jq, hook script)
#   2. Configure SessionStart hook in .claude/settings.local.json
#   3. Run initial indexation
#   4. Verify with leann list
#
# Usage:
#   scripts/setup-leann-sessions.sh [PROJECT_ROOT] [SESSION_ID]
#
# Arguments:
#   PROJECT_ROOT  Project root directory (default: $PWD)
#   SESSION_ID    Current session ID to exclude from indexation (optional)

set -euo pipefail

# --- Output helpers ---
info()  { echo "  ✓ $*"; }
warn()  { echo "  ⚠ $*" >&2; }
die()   { echo "  ✗ $*" >&2; exit 1; }

# --- Arguments ---
PROJECT_ROOT="${1:-$(pwd)}"
SESSION_ID="${2:-}"

# =========================================================
# Step 1: Prerequisites
# =========================================================
echo "=== Step 1: Checking prerequisites ==="

command -v leann >/dev/null 2>&1 || die "leann CLI not found on PATH"
command -v jq   >/dev/null 2>&1 || die "jq not found on PATH"

LEANN_BIN=$(readlink -f "$(command -v leann)" 2>/dev/null) || die "Cannot resolve leann symlink"
# leann binary is at <repo>/.venv/bin/leann
LEANN_REPO=$(dirname "$(dirname "$(dirname "$LEANN_BIN")")")

[ -f "$LEANN_REPO/apps/claude_code_rag.py" ] || die "apps/claude_code_rag.py not found in $LEANN_REPO"

HOOK_SCRIPT="$HOME/.claude/hooks/leann-index-sessions.sh"
[ -f "$HOOK_SCRIPT" ] || die "Hook script missing: $HOOK_SCRIPT"
[ -x "$HOOK_SCRIPT" ] || chmod +x "$HOOK_SCRIPT"

info "leann CLI: $(command -v leann)"
info "LEANN repo: $LEANN_REPO"
info "Hook script: $HOOK_SCRIPT"

# =========================================================
# Step 2: Configure SessionStart hook
# =========================================================
echo ""
echo "=== Step 2: Configuring SessionStart hook ==="

SETTINGS_DIR="$PROJECT_ROOT/.claude"
SETTINGS_FILE="$SETTINGS_DIR/settings.local.json"

mkdir -p "$SETTINGS_DIR"

HOOK_ENTRY='{
  "matcher": "startup",
  "hooks": [
    {
      "type": "command",
      "command": "~/.claude/hooks/leann-index-sessions.sh",
      "timeout": 120,
      "statusMessage": "Updating LEANN sessions index..."
    }
  ]
}'

if [ -f "$SETTINGS_FILE" ]; then
    # Check if hook already configured
    if jq -e '.hooks.SessionStart[]?.hooks[]? | select(.command | contains("leann-index-sessions"))' \
        "$SETTINGS_FILE" >/dev/null 2>&1; then
        info "Hook already configured — skipping"
    else
        # Merge into existing file: create or append to SessionStart array
        jq --argjson entry "$HOOK_ENTRY" '
            .hooks //= {} |
            .hooks.SessionStart //= [] |
            .hooks.SessionStart += [$entry]
        ' "$SETTINGS_FILE" > "${SETTINGS_FILE}.tmp" \
            && mv "${SETTINGS_FILE}.tmp" "$SETTINGS_FILE"
        info "Hook added to existing $SETTINGS_FILE"
    fi
else
    # Create new settings file
    jq -n --argjson entry "$HOOK_ENTRY" '{
        hooks: {
            SessionStart: [$entry]
        }
    }' > "$SETTINGS_FILE"
    info "Created $SETTINGS_FILE"
fi

# =========================================================
# Step 3: Initial indexation
# =========================================================
echo ""
echo "=== Step 3: Running initial indexation ==="

PROJECT_NAME=$(basename "$PROJECT_ROOT")

EXCLUDE_ARGS=()
if [ -n "$SESSION_ID" ]; then
    EXCLUDE_ARGS=(--exclude-session "$SESSION_ID")
fi

cd "$LEANN_REPO"
uv run python -m apps.claude_code_rag \
    --project-filter "$PROJECT_NAME" \
    "${EXCLUDE_ARGS[@]}" 2>&1

info "Indexation complete"

# =========================================================
# Step 4: Verify
# =========================================================
echo ""
echo "=== Step 4: Verification ==="

leann list 2>&1

echo ""
echo "=================================================="
info "LEANN session indexation is set up."
echo "  Index : ~/.leann/indexes/claude-code-sessions/"
echo "  Hook  : SessionStart (auto at each new session)"
echo "  Search: leann_search MCP tool, index 'claude-code-sessions'"
echo "=================================================="
