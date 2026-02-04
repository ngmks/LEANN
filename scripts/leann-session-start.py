#!/usr/bin/env python3
"""
LEANN SessionStart hook for Claude Code.

Executed via the shared wrapper ~/.leann/hooks/session-start.sh
which runs: cd $LEANN_ROOT && uv run python scripts/leann-session-start.py

Reads hook input from stdin (JSON), checks the whitelist, computes delta
for the current project, and either:
  - Does nothing (not whitelisted or no delta)
  - Runs inline indexation (small delta, blocking)
  - Prints a message for Claude to relay (large delta)

Stdout is visible to Claude as session context.
"""

from __future__ import annotations

import fcntl
import json
import re
import sys
import time
import urllib.request
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

WHITELIST_PATH = Path.home() / ".leann" / "whitelist.json"
DEFAULT_INDEX_DIR = Path.home() / ".leann" / "indexes" / "claude-code-sessions"
MANIFEST_FILENAME = "indexed_sessions.json"
LOCKFILE_PATH = Path.home() / ".leann" / "indexing.lock"
OLLAMA_CHECK_URL = "http://localhost:11434/api/tags"
OLLAMA_TIMEOUT = 2  # seconds

INLINE_THRESHOLD_LINES = 500


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def cwd_to_claude_dir(cwd: str) -> str:
    return re.sub(r"[^a-zA-Z0-9-]", "-", cwd)


def load_whitelist() -> dict:
    if WHITELIST_PATH.exists():
        try:
            return json.loads(WHITELIST_PATH.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    return {"projects": []}


def find_project_in_whitelist(cwd: str, whitelist: dict) -> dict | None:
    """Find the whitelist entry matching the given CWD."""
    cwd = str(Path(cwd).resolve())
    for p in whitelist.get("projects", []):
        if p.get("cwd") == cwd:
            return p
    return None


def check_ollama_available() -> bool:
    """Check if Ollama is running (2s timeout)."""
    try:
        req = urllib.request.Request(OLLAMA_CHECK_URL, method="GET")
        with urllib.request.urlopen(req, timeout=OLLAMA_TIMEOUT):
            return True
    except Exception:
        return False


def load_manifest() -> dict:
    path = DEFAULT_INDEX_DIR / MANIFEST_FILENAME
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def file_mtime_ms(path: Path) -> int:
    try:
        return int(path.stat().st_mtime * 1000)
    except OSError:
        return 0


def count_lines(path: Path) -> int:
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            return sum(1 for _ in f)
    except OSError:
        return 0


# ---------------------------------------------------------------------------
# Delta computation
# ---------------------------------------------------------------------------

def compute_delta(claude_dir: str) -> dict[str, Any]:
    """Compute indexation delta for a single project's claude_dir.

    Returns dict with keys:
      - new_sessions: int
      - modified_sessions: int
      - delta_lines: int  (total new lines across new + modified sessions)
      - session_details: list of (session_id, path, new_lines)
    """
    manifest = load_manifest()
    indexed = manifest.get("sessions", {})

    # Find the project directory under ~/.claude/projects/
    projects_base = Path.home() / ".claude" / "projects"
    project_dir = projects_base / claude_dir
    if not project_dir.is_dir():
        return {"new_sessions": 0, "modified_sessions": 0, "delta_lines": 0, "session_details": []}

    new_count = 0
    modified_count = 0
    total_delta_lines = 0
    details: list[tuple[str, Path, int]] = []

    for jsonl in project_dir.glob("*.jsonl"):
        sid = jsonl.stem
        mtime = file_mtime_ms(jsonl)

        if sid not in indexed:
            lines = count_lines(jsonl)
            new_count += 1
            total_delta_lines += lines
            details.append((sid, jsonl, lines))
        elif indexed[sid].get("mtime", 0) != mtime:
            old_lines = indexed[sid].get("lines_indexed", 0)
            current_lines = count_lines(jsonl)
            new_lines = max(0, current_lines - old_lines)
            if new_lines > 0:
                modified_count += 1
                total_delta_lines += new_lines
                details.append((sid, jsonl, new_lines))

    return {
        "new_sessions": new_count,
        "modified_sessions": modified_count,
        "delta_lines": total_delta_lines,
        "session_details": details,
    }


def estimate_time(delta_lines: int) -> float:
    """Rough estimate of indexation time in seconds."""
    return delta_lines / 50 + 4


# ---------------------------------------------------------------------------
# Inline indexation (small delta)
# ---------------------------------------------------------------------------

def run_inline_indexation(project_entry: dict) -> tuple[int, int]:
    """Run incremental indexation for a single project. Returns (sessions, chunks)."""
    # Import LEANN components (available via uv run)
    import argparse

    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "apps"))
    from claude_code_rag import ClaudeCodeRAG
    rag = ClaudeCodeRAG()
    # Build minimal args
    args = argparse.Namespace(
        session_dirs=[str(Path.home() / ".claude" / "projects")],
        project_filter=project_entry["project_name"],
        whitelist_file=None,
        granularity="turn",
        include_tool_names=True,
        no_tool_names=False,
        no_summaries=False,
        no_agents=False,
        max_text_per_turn=0,
        chunk_size=512,
        chunk_overlap=128,
        max_items=-1,
        index_dir=str(DEFAULT_INDEX_DIR),
        embedding_model="bge-m3",
        embedding_mode="ollama",
        embedding_host=None,
        embedding_api_base=None,
        embedding_api_key=None,
        backend_name="hnsw",
        graph_degree=32,
        build_complexity=64,
        search_complexity=32,
        no_compact=True,
        no_recompute=True,
        force_rebuild=False,
        top_k=20,
    )

    import asyncio

    async def _do_incremental():
        chunks, manifest = await rag._incremental_load(args)
        if chunks:
            index_path = str(Path(args.index_dir) / f"{rag.default_index_name}.leann")
            await rag._update_index(args, chunks, index_path)
            from claude_code_rag import _save_manifest
            _save_manifest(args.index_dir, manifest)
            return len(manifest.get("sessions", {})), len(chunks)
        return 0, 0

    sessions, chunks = asyncio.run(_do_incremental())
    return sessions, chunks


# ---------------------------------------------------------------------------
# Output helpers (stdout → Claude context)
# ---------------------------------------------------------------------------

def output_hook_context(message: str, *, system_message: str = "") -> None:
    """Print hookSpecificOutput JSON for Claude to see."""
    output: dict[str, Any] = {
        "hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": message,
        }
    }
    if system_message:
        output["systemMessage"] = system_message
    print(json.dumps(output))


def output_plain(message: str) -> None:
    """Print a plain text message (also visible to Claude via stdout)."""
    print(message)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    # Read hook input from stdin
    try:
        hook_input = json.loads(sys.stdin.read())
    except (json.JSONDecodeError, EOFError):
        hook_input = {}

    cwd = hook_input.get("cwd", "")
    if not cwd:
        sys.exit(0)

    # Check whitelist
    whitelist = load_whitelist()
    project_entry = find_project_in_whitelist(cwd, whitelist)
    if not project_entry:
        sys.exit(0)

    claude_dir = project_entry["claude_dir"]
    project_name = project_entry["project_name"]

    # Check Ollama availability
    if not check_ollama_available():
        output_hook_context(
            "[LEANN] Ollama n'est pas démarré. L'indexation automatique des "
            "sessions est désactivée. Pour l'activer, lance 'ollama serve' "
            "avant de démarrer Claude Code."
        )
        sys.exit(0)

    # Compute delta
    delta = compute_delta(claude_dir)
    if delta["delta_lines"] == 0:
        sys.exit(0)

    total_sessions = delta["new_sessions"] + delta["modified_sessions"]
    delta_lines = delta["delta_lines"]
    estimated_time = estimate_time(delta_lines)

    # Acquire lock (non-blocking — skip if another session is indexing)
    LOCKFILE_PATH.parent.mkdir(parents=True, exist_ok=True)
    lock_fd = open(LOCKFILE_PATH, "w")
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        # Another session is already indexing
        output_plain(
            f"[LEANN] Indexation déjà en cours par une autre session. "
            f"Delta pour '{project_name}' : {total_sessions} session(s), "
            f"{delta_lines} lignes."
        )
        lock_fd.close()
        sys.exit(0)

    try:
        if delta_lines < INLINE_THRESHOLD_LINES:
            # Small delta → inline blocking indexation
            t0 = time.monotonic()

            # Suppress verbose output during inline indexation
            import io
            old_stdout = sys.stdout
            sys.stdout = io.StringIO()
            try:
                sessions, chunks = run_inline_indexation(project_entry)
            finally:
                sys.stdout = old_stdout

            elapsed = time.monotonic() - t0
            output_plain(
                f"[LEANN] Index mis à jour : {total_sessions} session(s), "
                f"{chunks} chunks indexés en {elapsed:.1f}s."
            )
        else:
            # Large delta → imperative instruction for Claude to ask user
            leann_root = Path(__file__).resolve().parents[1]
            cmd = f"cd {leann_root} && uv run python scripts/leann-index-progress.py"
            output_hook_context(
                f"ACTION IMMÉDIATE REQUISE — Ne PAS attendre que "
                f"l'utilisateur pose une question. Tu DOIS exécuter cette "
                f"action TOUT DE SUITE, comme PREMIÈRE chose dans ta "
                f"PREMIÈRE réponse, AVANT tout autre contenu :\n"
                f"Utilise le tool AskUserQuestion IMMÉDIATEMENT avec la "
                f"question : « {total_sessions} sessions Claude Code "
                f"({delta_lines} lignes) ne sont pas encore indexées dans "
                f"LEANN. Lancer l'indexation (~{estimated_time:.0f}s) ? »\n"
                f"Si l'utilisateur accepte, exécute au PREMIER PLAN "
                f"(PAS en background, PAS run_in_background) avec un "
                f"timeout de 600000 : {cmd}",
                system_message=(
                    f"[LEANN] {total_sessions} session(s) non indexées "
                    f"détectées pour '{project_name}'."
                ),
            )
    finally:
        fcntl.flock(lock_fd, fcntl.LOCK_UN)
        lock_fd.close()


if __name__ == "__main__":
    main()
