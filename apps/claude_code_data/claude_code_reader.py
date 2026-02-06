"""
Claude Code session data reader.

Reads and processes Claude Code session JSONL files into Documents
suitable for RAG indexing. Supports main sessions, subagents, and
session summaries.
"""

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from llama_index.core import Document
from llama_index.core.readers.base import BaseReader

# Entry types we skip entirely
_SKIP_TYPES = frozenset({"system", "progress", "file-history-snapshot", "queue-operation"})


class ClaudeCodeReader(BaseReader):
    """
    Reader for Claude Code session JSONL files.

    Converts session transcripts into Documents preserving the
    question-answer context of each turn.
    """

    def __init__(
        self,
        granularity: str = "turn",
        include_tool_names: bool = True,
        include_summaries: bool = True,
        include_agents: bool = True,
        include_insights: bool = True,
        max_text_per_turn: int = 0,
    ) -> None:
        self.granularity = granularity
        self.include_tool_names = include_tool_names
        self.include_summaries = include_summaries
        self.include_agents = include_agents
        self.include_insights = include_insights
        self.max_text_per_turn = max_text_per_turn

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load_data(self, input_dir: str | None = None, **kwargs: Any) -> list[Document]:
        """Load Claude Code session data.

        Args:
            input_dir: Unused (kept for BaseReader compatibility).
            **kwargs:
                base_dirs: list of directories containing project folders.
                max_count: Maximum documents to return (-1 = all).
                include_metadata: Whether to attach metadata (default True).
                project_filter: Only index projects whose name contains this string.
        """
        base_dirs: list[str] = kwargs.get("base_dirs", [str(Path.home() / ".claude" / "projects")])
        max_count: int = kwargs.get("max_count", -1)
        include_metadata: bool = kwargs.get("include_metadata", True)
        project_filter: str | None = kwargs.get("project_filter", None)

        projects = self._discover_projects(base_dirs)
        if project_filter:
            projects = {k: v for k, v in projects.items() if project_filter.lower() in k.lower()}

        docs: list[Document] = []
        seen_sessions: set[str] = set()

        for project_name, project_info in sorted(projects.items()):
            project_dir = project_info["dir"]
            sessions_index = self._load_sessions_index(project_dir)

            # Discover JSONL files
            jsonl_files = sorted(project_dir.glob("*.jsonl"))
            for jsonl_path in jsonl_files:
                session_id = jsonl_path.stem
                if session_id in seen_sessions:
                    continue
                seen_sessions.add(session_id)

                session_meta = sessions_index.get(session_id, {})
                session_meta.setdefault("project_name", project_name)
                session_meta.setdefault("project_dir", str(project_dir))

                session_docs = self._parse_session_file(jsonl_path, session_meta, include_metadata)
                docs.extend(session_docs)

                # Subagents
                if self.include_agents:
                    session_dir = project_dir / session_id
                    for agent_path in self._discover_agent_files(session_dir):
                        agent_docs = self._parse_agent_file(
                            agent_path, session_meta, include_metadata
                        )
                        docs.extend(agent_docs)

                if 0 < max_count <= len(docs):
                    docs = docs[:max_count]
                    return docs

        print(f"ClaudeCodeReader: {len(docs)} documents from {len(seen_sessions)} sessions")
        return docs

    # ------------------------------------------------------------------
    # Project / session discovery
    # ------------------------------------------------------------------

    def _discover_projects(self, base_dirs: list[str]) -> dict[str, dict]:
        """Discover Claude Code projects in base directories.

        Returns dict mapping project_name -> {"dir": Path}.
        """
        projects: dict[str, dict] = {}
        for base in base_dirs:
            base_path = Path(base)
            if not base_path.is_dir():
                continue
            for child in sorted(base_path.iterdir()):
                if not child.is_dir():
                    continue
                # Must contain at least one JSONL or a sessions-index.json
                has_jsonl = any(child.glob("*.jsonl"))
                has_index = (child / "sessions-index.json").exists()
                if has_jsonl or has_index:
                    name = self._extract_project_name(child.name)
                    if name not in projects:
                        projects[name] = {"dir": child}
        return projects

    @staticmethod
    def _extract_project_name(dir_name: str) -> str:
        """Convert encoded dir name to human-readable project name.

        ``-home-mks-projects-casagreena-domotic-server``
        -> ``casagreena-domotic-server``
        """
        parts = dir_name.split("-")
        # Find the last occurrence of "projects" and take everything after
        try:
            idx = len(parts) - 1 - parts[::-1].index("projects")
            return "-".join(parts[idx + 1 :]) if idx + 1 < len(parts) else dir_name
        except ValueError:
            return dir_name

    def _load_sessions_index(self, project_dir: Path) -> dict[str, dict]:
        """Load sessions-index.json and return a dict keyed by sessionId."""
        index_path = project_dir / "sessions-index.json"
        if not index_path.exists():
            return {}
        try:
            data = json.loads(index_path.read_text(encoding="utf-8", errors="replace"))
            entries = data.get("entries", [])
            return {e["sessionId"]: e for e in entries if "sessionId" in e}
        except (json.JSONDecodeError, KeyError):
            return {}

    # ------------------------------------------------------------------
    # Main session parsing
    # ------------------------------------------------------------------

    def _parse_session_file(
        self,
        jsonl_path: Path,
        session_meta: dict,
        include_metadata: bool = True,
    ) -> list[Document]:
        """Parse a single session JSONL file into Documents."""
        entries = self._read_jsonl(jsonl_path)
        if not entries:
            return []

        session_id = jsonl_path.stem
        project_name = session_meta.get("project_name", "")
        docs: list[Document] = []

        # Collect summaries
        if self.include_summaries:
            for entry in entries:
                if entry.get("type") == "summary":
                    doc = self._make_summary_doc(entry, session_id, session_meta, include_metadata)
                    if doc:
                        docs.append(doc)

        # Collect turns
        if self.granularity == "session":
            doc = self._build_session_doc(entries, session_id, session_meta, include_metadata)
            if doc:
                docs.append(doc)
        elif self.granularity == "message":
            docs.extend(
                self._build_message_docs(entries, session_id, session_meta, include_metadata)
            )
        else:  # "turn" (default)
            docs.extend(self._build_turn_docs(entries, session_id, session_meta, include_metadata))

        return docs

    def _build_turn_docs(
        self,
        entries: list[dict],
        session_id: str,
        session_meta: dict,
        include_metadata: bool,
    ) -> list[Document]:
        """Group entries into user-turn + assistant-responses."""
        docs: list[Document] = []
        turn_index = 0
        current_user_text = ""
        assistant_parts: list[str] = []
        tool_names: list[str] = []
        turn_timestamp = ""
        turn_branch = ""
        turn_model = ""

        def _flush() -> None:
            nonlocal current_user_text, assistant_parts, tool_names
            nonlocal turn_index, turn_timestamp, turn_branch, turn_model
            if not current_user_text and not assistant_parts:
                return

            assistant_text = "\n".join(assistant_parts)
            text = self._format_turn_text(
                session_meta.get("project_name", ""),
                turn_branch,
                turn_timestamp,
                current_user_text,
                assistant_text,
                tool_names,
            )
            if self.max_text_per_turn > 0:
                text = text[: self.max_text_per_turn]

            turn_id = f"{session_id}:{turn_index}"
            meta = {}
            if include_metadata:
                meta = self._base_metadata(session_id, session_meta)
                meta.update(
                    {
                        "entry_type": "turn",
                        "turn_id": turn_id,
                        "turn_index": turn_index,
                        "timestamp": turn_timestamp,
                        "git_branch": turn_branch,
                        "model": turn_model,
                    }
                )

            docs.append(Document(text=text, metadata=meta))

            # Extract and emit insight documents
            if self.include_insights:
                for insight_body in self._extract_insights_from_text(assistant_text):
                    docs.append(
                        self._make_insight_doc(
                            insight_body,
                            session_id,
                            session_meta,
                            turn_id,
                            turn_timestamp,
                            turn_branch,
                            turn_model,
                            include_metadata,
                        )
                    )

            turn_index += 1
            current_user_text = ""
            assistant_parts = []
            tool_names = []

        for entry in entries:
            etype = entry.get("type", "")
            if etype in _SKIP_TYPES or etype == "summary":
                continue

            if etype == "user":
                msg = entry.get("message", {})
                text = self._extract_text_content(msg)
                if not text:
                    continue  # tool_result only
                # Start a new turn
                _flush()
                current_user_text = text
                turn_timestamp = entry.get("timestamp", "")
                turn_branch = entry.get("gitBranch", "")

            elif etype == "assistant":
                msg = entry.get("message", {})
                text, tools = self._extract_assistant_content(msg)
                if text:
                    assistant_parts.append(text)
                tool_names.extend(tools)
                if not turn_model:
                    turn_model = msg.get("model", "")

        _flush()
        return docs

    def _build_session_doc(
        self,
        entries: list[dict],
        session_id: str,
        session_meta: dict,
        include_metadata: bool,
    ) -> Document | None:
        """Concatenate entire session into one Document."""
        parts: list[str] = []
        all_tools: list[str] = []
        branch = ""
        model = ""
        ts = ""
        for entry in entries:
            etype = entry.get("type", "")
            if etype in _SKIP_TYPES or etype == "summary":
                continue
            if etype == "user":
                text = self._extract_text_content(entry.get("message", {}))
                if text:
                    parts.append(f"[User]: {text}")
                    if not ts:
                        ts = entry.get("timestamp", "")
                    if not branch:
                        branch = entry.get("gitBranch", "")
            elif etype == "assistant":
                text, tools = self._extract_assistant_content(entry.get("message", {}))
                if text:
                    parts.append(f"[Claude]: {text}")
                all_tools.extend(tools)
                if not model:
                    model = entry.get("message", {}).get("model", "")

        if not parts:
            return None

        project = session_meta.get("project_name", "")
        header = f"Project: {project}"
        if branch:
            header += f" | Branch: {branch}"
        if ts:
            header += f" | {self._format_date(ts)}"
        if self.include_tool_names and all_tools:
            header += "\n" + " ".join(f"[Tool: {t}]" for t in sorted(set(all_tools)))

        text = header + "\n\n" + "\n\n".join(parts)
        if self.max_text_per_turn > 0:
            text = text[: self.max_text_per_turn]

        meta = {}
        if include_metadata:
            meta = self._base_metadata(session_id, session_meta)
            meta.update(
                {
                    "entry_type": "session",
                    "timestamp": ts,
                    "git_branch": branch,
                    "model": model,
                }
            )
        return Document(text=text, metadata=meta)

    def _build_message_docs(
        self,
        entries: list[dict],
        session_id: str,
        session_meta: dict,
        include_metadata: bool,
    ) -> list[Document]:
        """One Document per meaningful message."""
        docs: list[Document] = []
        msg_index = 0
        for entry in entries:
            etype = entry.get("type", "")
            if etype in _SKIP_TYPES or etype == "summary":
                continue
            if etype == "user":
                text = self._extract_text_content(entry.get("message", {}))
                if not text:
                    continue
                prefix = f"[User]: {text}"
            elif etype == "assistant":
                text, tools = self._extract_assistant_content(entry.get("message", {}))
                if not text:
                    continue
                prefix = f"[Claude]: {text}"
                if self.include_tool_names and tools:
                    prefix += "\n" + " ".join(f"[Tool: {t}]" for t in tools)
            else:
                continue

            meta = {}
            if include_metadata:
                meta = self._base_metadata(session_id, session_meta)
                meta.update(
                    {
                        "entry_type": "message",
                        "turn_index": msg_index,
                        "timestamp": entry.get("timestamp", ""),
                        "git_branch": entry.get("gitBranch", ""),
                        "model": entry.get("message", {}).get("model", ""),
                    }
                )
            docs.append(Document(text=prefix, metadata=meta))
            msg_index += 1
        return docs

    # ------------------------------------------------------------------
    # Subagent parsing
    # ------------------------------------------------------------------

    @staticmethod
    def _discover_agent_files(session_dir: Path) -> list[Path]:
        """Glob for agent JSONL files inside a session directory."""
        subagents_dir = session_dir / "subagents"
        if not subagents_dir.is_dir():
            return []
        return sorted(subagents_dir.glob("agent-*.jsonl"))

    def _parse_agent_file(
        self,
        agent_path: Path,
        parent_session_meta: dict,
        include_metadata: bool = True,
    ) -> list[Document]:
        """Parse a subagent JSONL into Documents."""
        entries = self._read_jsonl(agent_path)
        if not entries:
            return []

        # Extract agent_id from filename: agent-aa9d70a.jsonl -> aa9d70a
        agent_id = agent_path.stem.replace("agent-", "")
        parent_session_id = parent_session_meta.get("sessionId", agent_path.parent.parent.name)
        project_name = parent_session_meta.get("project_name", "")

        docs: list[Document] = []
        prompt_text = ""
        agent_parts: list[str] = []
        tool_names: list[str] = []
        branch = ""
        model = ""
        ts = ""

        for entry in entries:
            etype = entry.get("type", "")
            if etype in _SKIP_TYPES or etype == "summary":
                continue

            if etype == "user":
                text = self._extract_text_content(entry.get("message", {}))
                if text and not prompt_text:
                    prompt_text = text
                    if not ts:
                        ts = entry.get("timestamp", "")
                    if not branch:
                        branch = entry.get("gitBranch", "")

            elif etype == "assistant":
                text, tools = self._extract_assistant_content(entry.get("message", {}))
                if text:
                    agent_parts.append(text)
                tool_names.extend(tools)
                if not model:
                    model = entry.get("message", {}).get("model", "")

        if not prompt_text and not agent_parts:
            return []

        # Format agent text
        header = f"Project: {project_name}"
        if branch:
            header += f" | Branch: {branch}"
        if ts:
            header += f" | {self._format_date(ts)}"
        header += f" | Agent: {agent_id}"

        # B1: Index only agent response, not the prompt (reduces noise from
        # boilerplate instructions). Store prompt in metadata for reference.
        parts = [header, ""]
        if agent_parts:
            agent_text = "\n".join(agent_parts)
            parts.append(f"[Agent]: {agent_text}")
        if self.include_tool_names and tool_names:
            parts.append(" ".join(f"[Tool: {t}]" for t in sorted(set(tool_names))))

        text = "\n".join(parts)
        if self.max_text_per_turn > 0:
            text = text[: self.max_text_per_turn]

        meta = {}
        if include_metadata:
            meta = self._base_metadata(parent_session_id, parent_session_meta)
            meta.update(
                {
                    "entry_type": "agent_turn",
                    "agent_id": agent_id,
                    "is_sidechain": True,
                    "session_id": parent_session_id,
                    "turn_id": f"{parent_session_id}:agent-{agent_id}",
                    "timestamp": ts,
                    "git_branch": branch,
                    "model": model,
                }
            )
            if prompt_text:
                meta["agent_prompt"] = prompt_text[:200]

        docs.append(Document(text=text, metadata=meta))
        return docs

    # ------------------------------------------------------------------
    # Summary documents
    # ------------------------------------------------------------------

    def _make_summary_doc(
        self,
        entry: dict,
        session_id: str,
        session_meta: dict,
        include_metadata: bool,
    ) -> Document | None:
        summary_text = entry.get("summary", "")
        if not summary_text:
            return None

        project = session_meta.get("project_name", "")
        created = session_meta.get("created", "")
        first_prompt = session_meta.get("firstPrompt", "")
        msg_count = session_meta.get("messageCount", "")
        branch = session_meta.get("gitBranch", "")

        text_parts = [
            f"Session Summary ({project}, {self._format_date(created) if created else 'unknown date'}):",
            summary_text,
        ]
        if first_prompt:
            # Truncate very long first prompts (e.g. expanded slash commands)
            fp = first_prompt[:200].strip()
            text_parts.append(f"First prompt: {fp}")
        info_bits = []
        if msg_count:
            info_bits.append(f"Messages: {msg_count}")
        if branch:
            info_bits.append(f"Branch: {branch}")
        if info_bits:
            text_parts.append(" | ".join(info_bits))

        text = "\n".join(text_parts)

        meta = {}
        if include_metadata:
            meta = self._base_metadata(session_id, session_meta)
            meta["entry_type"] = "summary"

        return Document(text=text, metadata=meta)

    # ------------------------------------------------------------------
    # Insight documents
    # ------------------------------------------------------------------

    _INSIGHT_RE = re.compile(
        r"`?★ Insight[─ ]*`?\s*\n(.*?)(?:\n\s*`?─{5,}`?|$)",
        re.DOTALL,
    )

    @staticmethod
    def _extract_insights_from_text(text: str) -> list[str]:
        """Extract ★ Insight blocks from assistant text.

        Returns a list of insight body strings (usually 0, 1, or 2).
        """
        return [
            m.group(1).strip()
            for m in ClaudeCodeReader._INSIGHT_RE.finditer(text)
            if m.group(1).strip()
        ]

    def _make_insight_doc(
        self,
        insight_text: str,
        session_id: str,
        session_meta: dict,
        turn_id: str,
        turn_timestamp: str,
        turn_branch: str,
        turn_model: str,
        include_metadata: bool,
    ) -> Document:
        """Create a Document for a single ★ Insight block."""
        project = session_meta.get("project_name", "")
        date_str = self._format_date(turn_timestamp) if turn_timestamp else "unknown date"

        text = f"Insight ({project}, {date_str}):\n{insight_text}"

        meta = {}
        if include_metadata:
            meta = self._base_metadata(session_id, session_meta)
            meta.update(
                {
                    "entry_type": "insight",
                    "turn_id": turn_id,
                    "timestamp": turn_timestamp,
                    "git_branch": turn_branch,
                    "model": turn_model,
                }
            )

        return Document(text=text, metadata=meta)

    # ------------------------------------------------------------------
    # Content extraction helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_text_content(message: dict) -> str:
        """Extract text content from a user message.

        Returns empty string if the message only contains tool_result blocks.
        """
        content = message.get("content", "")
        if isinstance(content, str):
            return content.strip()
        if isinstance(content, list):
            text_parts = []
            for block in content:
                if isinstance(block, dict):
                    if block.get("type") == "text":
                        text_parts.append(block.get("text", ""))
                    elif block.get("type") == "tool_result":
                        # Skip tool results
                        continue
                elif isinstance(block, str):
                    text_parts.append(block)
            return " ".join(text_parts).strip()
        return ""

    def _extract_assistant_content(self, message: dict) -> tuple[str, list[str]]:
        """Extract text + tool names from assistant message.

        Returns (text, tool_names). Ignores ``thinking`` blocks.
        """
        content = message.get("content", "")
        if isinstance(content, str):
            return content.strip(), []

        text_parts: list[str] = []
        tools: list[str] = []

        if isinstance(content, list):
            for block in content:
                if not isinstance(block, dict):
                    continue
                btype = block.get("type", "")
                if btype == "text":
                    t = block.get("text", "").strip()
                    if t:
                        text_parts.append(t)
                elif btype == "tool_use" and self.include_tool_names:
                    name = block.get("name", "")
                    if name:
                        tools.append(name)
                # Skip "thinking" blocks

        return "\n".join(text_parts), tools

    # ------------------------------------------------------------------
    # Formatting helpers
    # ------------------------------------------------------------------

    def _format_turn_text(
        self,
        project: str,
        branch: str,
        timestamp: str,
        user_text: str,
        assistant_text: str,
        tool_names: list[str],
    ) -> str:
        header = f"Project: {project}"
        if branch:
            header += f" | Branch: {branch}"
        if timestamp:
            header += f" | {self._format_date(timestamp)}"

        parts = [header, ""]
        if user_text:
            parts.append(f"[User]: {user_text}")
            parts.append("")
        if assistant_text:
            parts.append(f"[Claude]: {assistant_text}")
        if self.include_tool_names and tool_names:
            parts.append(" ".join(f"[Tool: {t}]" for t in sorted(set(tool_names))))

        return "\n".join(parts)

    @staticmethod
    def _format_date(ts: str) -> str:
        """Extract YYYY-MM-DD from an ISO timestamp string."""
        if not ts:
            return ""
        try:
            dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            return dt.strftime("%Y-%m-%d")
        except (ValueError, TypeError):
            return ts[:10] if len(ts) >= 10 else ts

    @staticmethod
    def _base_metadata(session_id: str, session_meta: dict) -> dict:
        return {
            "source": "claude_code_session",
            "session_id": session_id,
            "project_name": session_meta.get("project_name", ""),
            "session_summary": session_meta.get("summary", ""),
            "message_count": session_meta.get("messageCount", 0),
        }

    # ------------------------------------------------------------------
    # I/O
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
        except OSError:
            pass
        return entries
