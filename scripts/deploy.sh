#!/bin/bash
set -euo pipefail

# Deploy LEANN to local environment (pipx + Claude Code MCP)
#
# Usage:
#   ./scripts/deploy.sh          # Quick: verify editable install + restart MCP
#   ./scripts/deploy.sh --full   # Full: reinstall pipx packages + inject backend + restart MCP
#   ./scripts/deploy.sh --check  # Check only: show current install state, no changes

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." >/dev/null && pwd)"
CORE_PKG="$PROJECT_ROOT/packages/leann-core"
HNSW_PKG="$PROJECT_ROOT/packages/leann-backend-hnsw"
COMMANDS_SRC="$PROJECT_ROOT/scripts/claude-commands"
COMMANDS_DST="$HOME/.claude/commands"
SKILLS_SRC="$PROJECT_ROOT/scripts/claude-skills"
SKILLS_DST="$HOME/.claude/skills"
RULES_SRC="$PROJECT_ROOT/scripts/claude-rules"
RULES_DST="$HOME/.claude/rules"

MODE="${1:-quick}"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

info()  { echo -e "${GREEN}✓${NC} $1"; }
warn()  { echo -e "${YELLOW}⚠${NC} $1"; }
error() { echo -e "${RED}✗${NC} $1"; }

check_install() {
    echo "=== LEANN Install Status ==="
    echo ""

    # Check pipx
    if ! command -v pipx &>/dev/null; then
        error "pipx not found"
        return 1
    fi

    # Check leann-core in pipx
    if pipx list 2>/dev/null | grep -q "leann-core"; then
        local location
        location=$(pipx runpip leann-core show leann-core 2>/dev/null | grep "Editable project location" | cut -d: -f2- | xargs)
        if [ -n "$location" ]; then
            info "leann-core installed (editable: $location)"
        else
            warn "leann-core installed but NOT editable — run with --full"
        fi
    else
        error "leann-core not installed in pipx"
        return 1
    fi

    # Check HNSW backend
    if pipx runpip leann-core show leann-backend-hnsw &>/dev/null; then
        local hnsw_location
        hnsw_location=$(pipx runpip leann-core show leann-backend-hnsw 2>/dev/null | grep "Editable project location" | cut -d: -f2- | xargs)
        if [ -n "$hnsw_location" ]; then
            info "leann-backend-hnsw injected (editable: $hnsw_location)"
        else
            warn "leann-backend-hnsw installed but NOT editable — run with --full"
        fi
    else
        error "leann-backend-hnsw not injected — run with --full"
        return 1
    fi

    # Check CLIs
    for cmd in leann leann_mcp; do
        if command -v "$cmd" &>/dev/null; then
            info "$cmd available at $(which $cmd)"
        else
            error "$cmd not found in PATH"
        fi
    done

    # Check Claude Code slash commands
    local missing_cmds=0
    for cmd_file in "$COMMANDS_SRC"/*.md; do
        local cmd_name
        cmd_name="$(basename "$cmd_file")"
        if [ -f "$COMMANDS_DST/$cmd_name" ]; then
            info "Slash command /$(basename "$cmd_name" .md) installed"
        else
            warn "Slash command /$(basename "$cmd_name" .md) not installed — will install"
            missing_cmds=1
        fi
    done

    # Check Claude Code skills
    for skill_dir in "$SKILLS_SRC"/*/; do
        local skill_name
        skill_name="$(basename "$skill_dir")"
        if [ -d "$SKILLS_DST/$skill_name" ] && [ -f "$SKILLS_DST/$skill_name/SKILL.md" ]; then
            info "Skill /$skill_name installed"
        else
            warn "Skill /$skill_name not installed — will install"
        fi
    done

    # Check Claude Code rules
    for rule_file in "$RULES_SRC"/*.md; do
        local rule_name
        rule_name="$(basename "$rule_file")"
        if [ -f "$RULES_DST/$rule_name" ]; then
            info "Rule $rule_name installed"
        else
            warn "Rule $rule_name not installed — will install"
        fi
    done

    # Check MCP registration
    if command -v claude &>/dev/null; then
        if claude mcp list 2>/dev/null | grep -q "leann-server"; then
            info "MCP server 'leann-server' registered in Claude Code"
        else
            warn "MCP server 'leann-server' not registered — will register"
        fi
    fi

    echo ""
}

deploy_full() {
    echo "=== Full Deploy ==="
    echo ""

    # Step 1: Install leann-core editable via pipx
    info "Installing leann-core (editable)..."
    pipx install -e "$CORE_PKG" --force 2>&1 | tail -3

    # Step 2: Inject HNSW backend editable
    info "Injecting leann-backend-hnsw (editable)..."
    pipx inject leann-core -e "$HNSW_PKG" --force 2>&1 | tail -3

    # Step 3: Verify
    info "Verifying installation..."
    leann --help >/dev/null 2>&1 && info "leann CLI works" || error "leann CLI failed"
    echo '{}' | timeout 2 leann_mcp >/dev/null 2>&1; info "leann_mcp binary works"

    echo ""
}

deploy_quick() {
    echo "=== Quick Deploy ==="
    echo ""

    # Verify editable install is intact
    local location
    location=$(pipx runpip leann-core show leann-core 2>/dev/null | grep "Editable project location" | cut -d: -f2- | xargs)

    if [ "$location" = "$CORE_PKG" ]; then
        info "Editable install points to source — code changes are live"
    else
        warn "Editable install mismatch or missing — falling back to --full"
        deploy_full
        return
    fi

    echo ""
}

install_commands() {
    mkdir -p "$COMMANDS_DST"

    local installed=0
    for cmd_file in "$COMMANDS_SRC"/*.md; do
        local cmd_name
        cmd_name="$(basename "$cmd_file")"
        if [ -f "$COMMANDS_DST/$cmd_name" ] && diff -q "$cmd_file" "$COMMANDS_DST/$cmd_name" &>/dev/null; then
            info "/$(basename "$cmd_name" .md) already up to date"
        else
            cp "$cmd_file" "$COMMANDS_DST/$cmd_name"
            info "/$(basename "$cmd_name" .md) installed"
            installed=1
        fi
    done

    if [ "$installed" -eq 1 ]; then
        echo ""
        echo -e "  ${YELLOW}→ Restart Claude Code to pick up new slash commands${NC}"
    fi

    echo ""
}

install_skills() {
    local installed=0

    for skill_dir in "$SKILLS_SRC"/*/; do
        local skill_name
        skill_name="$(basename "$skill_dir")"
        local dst_dir="$SKILLS_DST/$skill_name"

        mkdir -p "$dst_dir"

        # Copy all files in the skill directory
        for skill_file in "$skill_dir"*; do
            local file_name
            file_name="$(basename "$skill_file")"
            if [ -f "$dst_dir/$file_name" ] && diff -q "$skill_file" "$dst_dir/$file_name" &>/dev/null; then
                : # Already up to date, silent
            else
                cp "$skill_file" "$dst_dir/$file_name"
                installed=1
            fi
        done

        if [ "$installed" -eq 1 ]; then
            info "Skill /$skill_name installed/updated"
        else
            info "Skill /$skill_name already up to date"
        fi
        installed=0
    done

    echo ""
}

install_rules() {
    mkdir -p "$RULES_DST"

    for rule_file in "$RULES_SRC"/*.md; do
        local rule_name
        rule_name="$(basename "$rule_file")"
        if [ -f "$RULES_DST/$rule_name" ] && diff -q "$rule_file" "$RULES_DST/$rule_name" &>/dev/null; then
            info "Rule $rule_name already up to date"
        else
            cp "$rule_file" "$RULES_DST/$rule_name"
            info "Rule $rule_name installed"
        fi
    done

    echo ""
}

ensure_mcp_registered() {
    if ! command -v claude &>/dev/null; then
        warn "claude CLI not found — skipping MCP registration"
        return
    fi

    # Only register if not already present
    if claude mcp list 2>/dev/null | grep -q "leann-server"; then
        info "MCP server already registered"
    else
        claude mcp add --scope user leann-server -- leann_mcp 2>&1 | tail -1
        info "MCP server registered"
    fi

    echo ""
    echo -e "  ${YELLOW}→ Run /mcp in Claude Code to reload the MCP server${NC}"
    echo ""
}

run_smoke_test() {
    echo "=== Smoke Test ==="
    echo ""

    # Test leann list
    if leann list >/dev/null 2>&1; then
        info "leann list works"
    else
        warn "leann list failed (no indexes?)"
    fi

    # Test MCP tool schema includes project param
    local schema
    schema=$(printf '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}\n{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}\n' | timeout 5 leann_mcp 2>/dev/null)
    if echo "$schema" | grep -q '"project"'; then
        info "MCP schema includes 'project' parameter"
    else
        warn "MCP schema missing 'project' parameter"
    fi

    echo ""
}

# --- Main ---

case "$MODE" in
    --check)
        check_install
        ;;
    --full)
        check_install
        deploy_full
        install_commands
        install_skills
        install_rules
        ensure_mcp_registered
        run_smoke_test
        info "Full deploy complete!"
        ;;
    quick|*)
        check_install
        deploy_quick
        install_commands
        install_skills
        install_rules
        ensure_mcp_registered
        run_smoke_test
        info "Quick deploy complete!"
        ;;
esac
