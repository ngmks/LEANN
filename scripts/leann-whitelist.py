#!/usr/bin/env python3
"""
Manage the LEANN whitelist for Claude Code session indexing.

This standalone script (stdlib only, no LEANN dependency) handles:
  - Adding/removing projects to ~/.leann/whitelist.json
  - Setting up / tearing down per-project SessionStart hooks
    in {project}/.claude/settings.local.json

Usage:
    python3 leann-whitelist.py add [CWD]
    python3 leann-whitelist.py remove [CWD]
    python3 leann-whitelist.py list
"""

from __future__ import annotations

import json
import os
import re
import stat
import sys
from datetime import datetime, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

WHITELIST_PATH = Path.home() / ".leann" / "whitelist.json"
HOOK_WRAPPER_PATH = Path.home() / ".leann" / "hooks" / "session-start.sh"

# The hook entry injected into .claude/settings.local.json
HOOK_COMMAND = "$HOME/.leann/hooks/session-start.sh"
HOOK_TIMEOUT = 30

# Sentinel used to identify our hook entries when merging / removing
HOOK_SENTINEL = "session-start.sh"


# ---------------------------------------------------------------------------
# CWD ↔ Claude dir helpers
# ---------------------------------------------------------------------------

def cwd_to_claude_dir(cwd: str) -> str:
    """Convert an absolute path to the Claude project directory name.

    /home/mks/projects/foo-bar  →  -home-mks-projects-foo-bar
    """
    return re.sub(r"[^a-zA-Z0-9-]", "-", cwd)


def extract_project_name(claude_dir: str) -> str:
    """Extract a human-readable project name from a Claude dir name.

    -home-mks-projects-casagreena-domotic-server
    →  casagreena-domotic-server
    """
    parts = claude_dir.split("-")
    try:
        idx = len(parts) - 1 - parts[::-1].index("projects")
        return "-".join(parts[idx + 1:]) if idx + 1 < len(parts) else claude_dir
    except ValueError:
        return claude_dir


# ---------------------------------------------------------------------------
# Whitelist I/O
# ---------------------------------------------------------------------------

def load_whitelist() -> dict:
    if WHITELIST_PATH.exists():
        try:
            return json.loads(WHITELIST_PATH.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    return {"projects": []}


def save_whitelist(wl: dict) -> None:
    WHITELIST_PATH.parent.mkdir(parents=True, exist_ok=True)
    WHITELIST_PATH.write_text(
        json.dumps(wl, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


# ---------------------------------------------------------------------------
# Hook wrapper (shared bash script)
# ---------------------------------------------------------------------------

_HOOK_WRAPPER_CONTENT = """\
#!/bin/bash
# LEANN SessionStart hook — derive LEANN_ROOT from the editable pipx install.
# Shared by all whitelisted projects.
LEANN_PYTHON="$(dirname "$(readlink -f "$(which leann)")")/python"
LEANN_ROOT="$("$LEANN_PYTHON" -c 'from pathlib import Path; import leann; print(Path(leann.__file__).resolve().parents[4])')"
cd "$LEANN_ROOT" && uv run python scripts/leann-session-start.py
"""


def ensure_hook_wrapper() -> None:
    """Create ~/.leann/hooks/session-start.sh if it doesn't exist."""
    if HOOK_WRAPPER_PATH.exists():
        return
    HOOK_WRAPPER_PATH.parent.mkdir(parents=True, exist_ok=True)
    HOOK_WRAPPER_PATH.write_text(_HOOK_WRAPPER_CONTENT, encoding="utf-8")
    # chmod +x
    HOOK_WRAPPER_PATH.chmod(
        HOOK_WRAPPER_PATH.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH
    )


# ---------------------------------------------------------------------------
# Project hook management (.claude/settings.local.json)
# ---------------------------------------------------------------------------

def _settings_path(cwd: str) -> Path:
    return Path(cwd) / ".claude" / "settings.local.json"


def _load_settings(path: Path) -> dict:
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def _save_settings(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _has_leann_hook(settings: dict) -> bool:
    """Check if settings already contain our SessionStart hook."""
    for matcher in settings.get("hooks", {}).get("SessionStart", []):
        for hook in matcher.get("hooks", []):
            if HOOK_SENTINEL in hook.get("command", ""):
                return True
    return False


def setup_project_hook(cwd: str) -> None:
    """Add the LEANN SessionStart hook to the project's local settings."""
    ensure_hook_wrapper()

    path = _settings_path(cwd)
    settings = _load_settings(path)

    if _has_leann_hook(settings):
        print(f"  Hook déjà présent dans {path}")
        return

    leann_matcher = {
        "hooks": [
            {
                "type": "command",
                "command": HOOK_COMMAND,
                "timeout": HOOK_TIMEOUT,
            }
        ]
    }

    settings.setdefault("hooks", {})
    settings["hooks"].setdefault("SessionStart", [])
    settings["hooks"]["SessionStart"].append(leann_matcher)

    _save_settings(path, settings)
    print(f"  Hook ajouté dans {path}")


def remove_project_hook(cwd: str) -> None:
    """Remove the LEANN SessionStart hook from the project's local settings."""
    path = _settings_path(cwd)
    settings = _load_settings(path)

    if not settings:
        return

    hooks = settings.get("hooks", {})
    session_start = hooks.get("SessionStart", [])

    # Filter out matchers containing our hook
    filtered = []
    for matcher in session_start:
        inner_hooks = matcher.get("hooks", [])
        remaining = [h for h in inner_hooks if HOOK_SENTINEL not in h.get("command", "")]
        if remaining:
            matcher["hooks"] = remaining
            filtered.append(matcher)

    if filtered:
        hooks["SessionStart"] = filtered
    else:
        hooks.pop("SessionStart", None)

    if not hooks:
        settings.pop("hooks", None)

    if not settings:
        # Empty settings → delete file
        try:
            path.unlink()
            print(f"  Fichier supprimé (vide) : {path}")
        except OSError:
            pass
    else:
        _save_settings(path, settings)
        print(f"  Hook retiré de {path}")


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def cmd_add(cwd: str) -> None:
    cwd = str(Path(cwd).resolve())
    claude_dir = cwd_to_claude_dir(cwd)
    project_name = extract_project_name(claude_dir)

    wl = load_whitelist()

    # Check for duplicates
    for p in wl["projects"]:
        if p["cwd"] == cwd:
            print(f"✓ Projet déjà dans la whitelist : {project_name} ({cwd})")
            # Ensure hook is set up anyway
            setup_project_hook(cwd)
            print("\n⚠  Relancez Claude Code pour activer l'indexation automatique.")
            return

    wl["projects"].append({
        "cwd": cwd,
        "claude_dir": claude_dir,
        "project_name": project_name,
        "added": datetime.now(timezone.utc).isoformat(),
    })
    save_whitelist(wl)
    print(f"✓ Projet ajouté à la whitelist : {project_name} ({cwd})")

    setup_project_hook(cwd)

    print("\n⚠  Relancez Claude Code pour activer l'indexation automatique.")


def cmd_remove(cwd: str) -> None:
    cwd = str(Path(cwd).resolve())
    claude_dir = cwd_to_claude_dir(cwd)
    project_name = extract_project_name(claude_dir)

    wl = load_whitelist()
    original_count = len(wl["projects"])
    wl["projects"] = [p for p in wl["projects"] if p["cwd"] != cwd]

    if len(wl["projects"]) == original_count:
        print(f"✗ Projet non trouvé dans la whitelist : {project_name} ({cwd})")
        return

    save_whitelist(wl)
    print(f"✓ Projet retiré de la whitelist : {project_name} ({cwd})")

    remove_project_hook(cwd)

    print("\n⚠  Relancez Claude Code pour désactiver le hook.")
    print("i  Les données déjà indexées restent disponibles via la recherche MCP.")


def cmd_list() -> None:
    wl = load_whitelist()
    projects = wl.get("projects", [])

    if not projects:
        print("Aucun projet dans la whitelist.")
        print("Utilisez 'leann-whitelist.py add' pour ajouter un projet.")
        return

    print(f"Projets whitelistés ({len(projects)}) :\n")
    for p in projects:
        print(f"  • {p['project_name']}")
        print(f"    CWD: {p['cwd']}")
        print(f"    Claude dir: {p['claude_dir']}")
        print(f"    Ajouté: {p.get('added', '?')}")
        print()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: leann-whitelist.py <add|remove|list> [CWD]")
        sys.exit(1)

    command = sys.argv[1].lower()
    cwd = sys.argv[2] if len(sys.argv) > 2 else os.getcwd()

    if command == "add":
        cmd_add(cwd)
    elif command == "remove":
        cmd_remove(cwd)
    elif command == "list":
        cmd_list()
    else:
        print(f"Commande inconnue : {command}")
        print("Usage: leann-whitelist.py <add|remove|list> [CWD]")
        sys.exit(1)


if __name__ == "__main__":
    main()
