#!/usr/bin/env python3
"""
Extract task lifecycle data from recent Claude Code sessions.

Parses session JSONL files to find TaskCreate/TaskUpdate tool calls,
builds a state machine per session, and outputs incomplete tasks as JSON.

Serves as a safety net for sessions where MEMORY.md was not updated
(crashes, interruptions).

Usage:
    python3 scripts/leann-extract-tasks.py --claude-dir "<CLAUDE_DIR>" [--sessions 5]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def load_sessions_index(project_dir: Path) -> dict[str, dict]:
    """Load sessions-index.json as a dict keyed by sessionId."""
    index_path = project_dir / "sessions-index.json"
    if not index_path.exists():
        return {}
    try:
        data = json.loads(index_path.read_text(encoding="utf-8"))
        return {e["sessionId"]: e for e in data.get("entries", []) if "sessionId" in e}
    except (json.JSONDecodeError, OSError) as e:
        print(f"[warn] Cannot read sessions-index.json: {e}", file=sys.stderr)
        return {}


def discover_recent_sessions(
    project_dir: Path, n: int
) -> list[tuple[str, Path, dict]]:
    """Return (session_id, jsonl_path, index_meta) for N most recent sessions.

    Always uses filesystem mtime for ordering (sessions-index.json can be stale).
    Uses sessions-index.json only for metadata (summary, gitBranch, etc.).
    """
    index_by_id = load_sessions_index(project_dir)

    jsonl_files = sorted(
        project_dir.glob("*.jsonl"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )

    results = []
    for f in jsonl_files[:n]:
        sid = f.stem
        meta = index_by_id.get(sid, {})
        results.append((sid, f, meta))
    return results


def extract_session_metadata(jsonl_path: Path) -> dict:
    """Extract basic metadata (timestamp, gitBranch) from the first JSONL entry."""
    try:
        with open(jsonl_path, encoding="utf-8", errors="replace") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                    return {
                        "timestamp": entry.get("timestamp", ""),
                        "gitBranch": entry.get("gitBranch", ""),
                    }
                except json.JSONDecodeError:
                    continue
    except OSError:
        pass
    return {}


def extract_tasks_from_session(jsonl_path: Path) -> tuple[dict[str, dict], str]:
    """Parse a session JSONL for task tool calls and last assistant message.

    Returns (tasks_dict, last_message_excerpt).
    tasks_dict maps task_id -> {subject, description, status, activeForm}.
    """
    tasks: dict[str, dict] = {}
    next_id = 1
    last_text = ""

    try:
        with open(jsonl_path, encoding="utf-8", errors="replace") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue

                if entry.get("type") != "assistant":
                    continue
                if entry.get("isSidechain"):
                    continue

                content = entry.get("message", {}).get("content", [])
                if not isinstance(content, list):
                    continue

                # Extract text (for last message)
                for block in content:
                    if not isinstance(block, dict):
                        continue
                    if block.get("type") == "text":
                        t = block.get("text", "").strip()
                        if t:
                            last_text = t

                # Extract task tool calls
                for block in content:
                    if not isinstance(block, dict):
                        continue
                    if block.get("type") != "tool_use":
                        continue

                    name = block.get("name", "")
                    inp = block.get("input", {})

                    if name == "TaskCreate":
                        tid = str(next_id)
                        next_id += 1
                        tasks[tid] = {
                            "id": tid,
                            "subject": inp.get("subject", ""),
                            "description": inp.get("description", ""),
                            "status": "pending",
                            "activeForm": inp.get("activeForm", ""),
                        }

                    elif name == "TaskUpdate":
                        tid = inp.get("taskId", "")
                        if tid not in tasks:
                            continue  # Unknown ID, skip
                        new_status = inp.get("status")
                        if new_status:
                            tasks[tid]["status"] = new_status
                        new_subject = inp.get("subject")
                        if new_subject:
                            tasks[tid]["subject"] = new_subject

    except OSError as e:
        print(f"[warn] Cannot read {jsonl_path}: {e}", file=sys.stderr)

    # Truncate last message
    if len(last_text) > 500:
        last_text = last_text[:497] + "..."

    return tasks, last_text


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Extract task lifecycle from recent Claude Code sessions."
    )
    parser.add_argument(
        "--claude-dir",
        required=True,
        help="Claude project directory name (e.g. -home-mks-projects-leann-fork)",
    )
    parser.add_argument(
        "--sessions",
        type=int,
        default=5,
        help="Number of most recent sessions to scan (default: 5)",
    )
    parser.add_argument(
        "--project-dir",
        default=str(Path.home() / ".claude" / "projects"),
        help="Path to ~/.claude/projects (default: auto)",
    )
    args = parser.parse_args()

    project_dir = Path(args.project_dir) / args.claude_dir
    if not project_dir.is_dir():
        print(
            json.dumps({"sessions_scanned": 0, "sessions": [], "total_incomplete": 0})
        )
        return

    recent = discover_recent_sessions(project_dir, args.sessions)

    sessions_output = []
    total_incomplete = 0

    for sid, path, meta in recent:
        tasks, last_excerpt = extract_tasks_from_session(path)

        all_tasks = list(tasks.values())
        incomplete = [
            {"id": t["id"], "subject": t["subject"], "status": t["status"]}
            for t in all_tasks
            if t["status"] not in ("completed", "deleted")
        ]
        total_incomplete += len(incomplete)

        # Extract date and branch: prefer index metadata, fallback to JSONL
        date = ""
        branch = meta.get("gitBranch", "")
        if meta.get("modified"):
            date = meta["modified"][:10]
        elif meta.get("created"):
            date = meta["created"][:10]

        if not date or not branch:
            jsonl_meta = extract_session_metadata(path)
            if not date and jsonl_meta.get("timestamp"):
                date = jsonl_meta["timestamp"][:10]
            if not branch:
                branch = jsonl_meta.get("gitBranch", "")

        sessions_output.append(
            {
                "session_id": sid,
                "date": date,
                "branch": branch,
                "summary": meta.get("summary", ""),
                "incomplete_tasks": incomplete,
                "total_tasks": len(all_tasks),
                "last_message_excerpt": last_excerpt,
            }
        )

    output = {
        "sessions_scanned": len(recent),
        "sessions": sessions_output,
        "total_incomplete": total_incomplete,
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
