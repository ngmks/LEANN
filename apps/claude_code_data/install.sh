#!/bin/bash
# install.sh — Deploy Claude Code skill and hook via symlinks.
#
# Creates symlinks from ~/.claude/ to the repo so that:
#   - /index-sessions skill is available across all projects
#   - SessionStart hook auto-indexes sessions
#
# Usage:
#   apps/claude_code_data/install.sh            # Install
#   apps/claude_code_data/install.sh --uninstall # Remove symlinks

set -euo pipefail

# --- Resolve repo paths ---
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SKILL_SRC="$SCRIPT_DIR/skill"
HOOK_SRC="$SCRIPT_DIR/hooks/leann-index-sessions.sh"

SKILL_DST="$HOME/.claude/skills/index-sessions"
HOOK_DST="$HOME/.claude/hooks/leann-index-sessions.sh"

info() { echo "  ✓ $*"; }
warn() { echo "  ⚠ $*" >&2; }
die()  { echo "  ✗ $*" >&2; exit 1; }

# --- Uninstall ---
if [ "${1:-}" = "--uninstall" ]; then
    echo "Uninstalling Claude Code skill and hook..."
    [ -L "$SKILL_DST" ] && rm "$SKILL_DST" && info "Removed skill symlink"
    [ -L "$HOOK_DST" ]  && rm "$HOOK_DST"  && info "Removed hook symlink"
    echo "Done."
    exit 0
fi

# --- Validate sources ---
[ -f "$SKILL_SRC/SKILL.md" ] || die "SKILL.md not found at $SKILL_SRC"
[ -f "$HOOK_SRC" ]           || die "Hook script not found at $HOOK_SRC"

# --- Install skill symlink ---
echo "Installing Claude Code skill and hook..."
mkdir -p "$HOME/.claude/skills" "$HOME/.claude/hooks"

# Remove existing (file or symlink) before creating new symlink
[ -e "$SKILL_DST" ] || [ -L "$SKILL_DST" ] && rm -rf "$SKILL_DST"
ln -s "$SKILL_SRC" "$SKILL_DST"
info "Skill: $SKILL_DST → $SKILL_SRC"

# --- Install hook symlink ---
[ -e "$HOOK_DST" ] || [ -L "$HOOK_DST" ] && rm -f "$HOOK_DST"
ln -s "$HOOK_SRC" "$HOOK_DST"
info "Hook:  $HOOK_DST → $HOOK_SRC"

# --- Verify ---
echo ""
echo "Verifying..."
[ -f "$SKILL_DST/SKILL.md" ]           || die "Skill symlink broken"
[ -x "$HOOK_DST" ] || chmod +x "$HOOK_DST"
[ -f "$HOOK_DST" ]                     || die "Hook symlink broken"
info "Skill SKILL.md readable"
info "Hook script executable"

echo ""
echo "=================================================="
info "Installation complete."
echo "  Skill : /index-sessions (available in all projects)"
echo "  Hook  : ~/.claude/hooks/leann-index-sessions.sh"
echo ""
echo "  Next: run /index-sessions in a project to set up"
echo "  auto-indexation for that project."
echo "=================================================="
