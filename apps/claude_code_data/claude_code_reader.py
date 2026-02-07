"""
Claude Code JSONL session reader.

Reads Claude Code conversation transcripts stored as JSONL files
in ~/.claude/projects/<encoded-dir>/*.jsonl.
Each line is a JSON event: user message, assistant response, tool call, etc.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from llama_index.core import Document
from llama_index.core.readers.base import BaseReader

logger = logging.getLogger(__name__)

# Entry types that carry no useful conversational content
_SKIP_TYPES = frozenset(
    {
        "system",
        "progress",
        "file-history-snapshot",
        "queue-operation",
    }
)


class ClaudeCodeReader(BaseReader):
    """Reader for Claude Code JSONL session transcripts.

    Groups consecutive JSONL entries into turns (one user message +
    following assistant responses) and returns them as Documents with
    rich metadata (session_id, project, branch, timestamp).
    """

    def __init__(
        self,
        granularity: str = "turn",
        include_agents: bool = True,
    ) -> None:
        self.granularity = granularity
        self.include_agents = include_agents

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load_data(self, input_dir: str | None = None, **kwargs: Any) -> list[Document]:
        """Load Claude Code session data.

        Keyword Args:
            base_dirs: List of directories containing Claude Code projects
                       (default: ~/.claude/projects).
            max_count: Maximum number of sessions to process (-1 = all).
            include_metadata: Include metadata in documents (default True).
            project_filter: Only process projects whose name contains this string.
            exclude_sessions: Set of session IDs to skip.
        """
        base_dirs = kwargs.get("base_dirs") or [str(Path.home() / ".claude" / "projects")]
        max_count: int = kwargs.get("max_count", -1)
        include_metadata: bool = kwargs.get("include_metadata", True)
        project_filter: str | None = kwargs.get("project_filter")
        exclude_sessions: set[str] = set(kwargs.get("exclude_sessions") or [])

        # Expand ~ and resolve
        base_dirs = [str(Path(d).expanduser().resolve()) for d in base_dirs]

        projects = self._discover_projects(base_dirs)
        if project_filter:
            projects = {
                k: v for k, v in projects.items() if project_filter.lower() in v["name"].lower()
            }

        if not projects:
            print("No Claude Code projects found.")
            return []

        print(f"Found {len(projects)} project(s)")

        all_docs: list[Document] = []
        sessions_processed = 0

        for proj_dir, proj_info in projects.items():
            jsonl_files = sorted(Path(proj_dir).glob("*.jsonl"))
            if not jsonl_files:
                continue

            for jsonl_path in jsonl_files:
                session_id = jsonl_path.stem

                # Skip agents files at top level (handled separately)
                if session_id.startswith("agent-"):
                    continue
                if session_id in exclude_sessions:
                    continue
                if 0 < max_count <= sessions_processed:
                    break

                entries = self._read_jsonl(jsonl_path)
                if not entries:
                    continue

                # Extract session-level metadata from first entry
                first = entries[0]
                session_meta = {
                    "session_id": first.get("sessionId", session_id),
                    "project_name": proj_info["name"],
                    "project_dir": proj_info["encoded_dir"],
                    "git_branch": first.get("gitBranch", ""),
                    "cwd": first.get("cwd", ""),
                }

                docs = self._build_turn_docs(entries, session_id, session_meta, include_metadata)
                all_docs.extend(docs)

                # Include subagent files if requested
                if self.include_agents:
                    agents_dir = jsonl_path.parent / "subagents"
                    if agents_dir.is_dir():
                        for agent_file in sorted(agents_dir.glob("agent-*.jsonl")):
                            agent_entries = self._read_jsonl(agent_file)
                            if agent_entries:
                                agent_meta = {
                                    **session_meta,
                                    "is_subagent": True,
                                    "agent_file": agent_file.name,
                                }
                                agent_docs = self._build_turn_docs(
                                    agent_entries,
                                    session_id,
                                    agent_meta,
                                    include_metadata,
                                )
                                all_docs.extend(agent_docs)

                sessions_processed += 1

            if 0 < max_count <= sessions_processed:
                break

        print(f"Created {len(all_docs)} documents from {sessions_processed} sessions")
        return all_docs

    # ------------------------------------------------------------------
    # Project discovery
    # ------------------------------------------------------------------

    def _discover_projects(self, base_dirs: list[str]) -> dict[str, dict]:
        """Discover Claude Code project directories.

        Returns:
            Dict mapping directory path -> {name, encoded_dir}
        """
        projects: dict[str, dict] = {}
        for base in base_dirs:
            base_path = Path(base)
            if not base_path.is_dir():
                continue
            for child in sorted(base_path.iterdir()):
                if not child.is_dir():
                    continue
                # Must contain at least one .jsonl file
                if not any(child.glob("*.jsonl")):
                    continue
                projects[str(child)] = {
                    "name": self._extract_project_name(child.name),
                    "encoded_dir": child.name,
                }
        return projects

    @staticmethod
    def _extract_project_name(dir_name: str) -> str:
        """Convert encoded dir name to human-readable project name.

        '-home-mks-projects-leann-fork' -> 'leann-fork'
        """
        parts = dir_name.split("-")
        # Skip leading empty part (from leading dash) and path segments
        # like 'home', username, 'projects'
        # Strategy: take the last meaningful segment(s)
        clean = [p for p in parts if p]
        if not clean:
            return dir_name

        # Find 'projects' marker and take everything after it
        try:
            idx = clean.index("projects")
            remainder = clean[idx + 1 :]
            if remainder:
                return "-".join(remainder)
        except ValueError:
            pass

        # Fallback: last segment
        return clean[-1] if clean else dir_name

    # ------------------------------------------------------------------
    # JSONL reading
    # ------------------------------------------------------------------

    @staticmethod
    def _read_jsonl(path: Path) -> list[dict]:
        """Read a JSONL file, skipping malformed lines."""
        entries: list[dict] = []
        try:
            with open(path, encoding="utf-8", errors="replace") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entries.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
        except OSError as e:
            logger.warning(f"Cannot read {path}: {e}")
        return entries

    # ------------------------------------------------------------------
    # Turn building
    # ------------------------------------------------------------------

    def _build_turn_docs(
        self,
        entries: list[dict],
        session_id: str,
        session_meta: dict,
        include_metadata: bool = True,
    ) -> list[Document]:
        """Group entries into turns and create Documents."""
        turns: list[dict] = []
        current_turn: dict | None = None

        for entry in entries:
            entry_type = entry.get("type", "")

            # Skip non-conversational types
            if entry_type in _SKIP_TYPES:
                continue

            # Skip isMeta boilerplate (skill expansions etc.)
            msg = entry.get("message", {})
            if msg.get("isMeta"):
                continue

            if entry_type == "user":
                # Start a new turn
                if current_turn and current_turn.get("parts"):
                    turns.append(current_turn)
                text = self._extract_text_content(msg)
                if not text or not text.strip():
                    current_turn = None
                    continue
                current_turn = {
                    "user_text": text,
                    "parts": [],
                    "tools": [],
                    "timestamp": entry.get("timestamp", ""),
                    "git_branch": entry.get("gitBranch", session_meta.get("git_branch", "")),
                }

            elif entry_type == "assistant" and current_turn is not None:
                text, tool_names = self._extract_assistant_content(msg)
                if text:
                    current_turn["parts"].append(text)
                current_turn["tools"].extend(tool_names)

        # Don't forget the last turn
        if current_turn and current_turn.get("parts"):
            turns.append(current_turn)

        # Convert turns to Documents
        docs: list[Document] = []
        project_name = session_meta.get("project_name", "")
        for turn in turns:
            branch = turn.get("git_branch", "")
            ts = turn.get("timestamp", "")
            # Format timestamp to date only if possible
            date_str = ""
            if ts:
                try:
                    dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                    date_str = dt.strftime("%Y-%m-%d")
                except (ValueError, TypeError):
                    date_str = ts[:10] if len(ts) >= 10 else ts

            # Build header with metadata for implicit semantic filtering
            header_parts = []
            if project_name:
                header_parts.append(f"Project: {project_name}")
            if branch:
                header_parts.append(f"Branch: {branch}")
            if date_str:
                header_parts.append(date_str)
            header = " | ".join(header_parts)

            # Build text content
            assistant_text = "\n".join(turn["parts"])
            tools_line = ""
            if turn["tools"]:
                unique_tools = list(dict.fromkeys(turn["tools"]))  # dedupe, preserve order
                tools_line = f"\n[Tools: {', '.join(unique_tools)}]"

            text = (
                f"{header}\n[User]: {turn['user_text']}\n[Assistant]: {assistant_text}{tools_line}"
            )

            metadata = {}
            if include_metadata:
                metadata = {
                    "session_id": session_id,
                    "project_name": project_name,
                    "git_branch": branch,
                    "timestamp": ts,
                    "entry_type": "turn",
                    "source": "Claude Code",
                }
                if session_meta.get("is_subagent"):
                    metadata["is_subagent"] = True
                    metadata["agent_file"] = session_meta.get("agent_file", "")

            docs.append(Document(text=text, metadata=metadata))

        return docs

    # ------------------------------------------------------------------
    # Content extraction
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_text_content(message: dict) -> str:
        """Extract text from a message's content field.

        Handles both string content and array-of-blocks content.
        """
        content = message.get("content", "")
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts = []
            for block in content:
                if isinstance(block, str):
                    parts.append(block)
                elif isinstance(block, dict):
                    btype = block.get("type", "")
                    if btype == "text":
                        parts.append(block.get("text", ""))
            return "\n".join(parts)
        return ""

    @staticmethod
    def _extract_assistant_content(message: dict) -> tuple[str, list[str]]:
        """Extract text and tool names from an assistant message.

        Skips 'thinking' and 'tool_result' blocks.
        Returns (text, list_of_tool_names).
        """
        content = message.get("content", "")
        if isinstance(content, str):
            return content, []

        text_parts: list[str] = []
        tool_names: list[str] = []

        if isinstance(content, list):
            for block in content:
                if not isinstance(block, dict):
                    continue
                btype = block.get("type", "")
                if btype == "text":
                    text_parts.append(block.get("text", ""))
                elif btype == "tool_use":
                    name = block.get("name", "")
                    if name:
                        tool_names.append(name)
                # Skip: thinking, tool_result

        return "\n".join(text_parts), tool_names
