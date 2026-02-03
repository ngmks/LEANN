"""
Claude Code RAG — index and query Claude Code session transcripts.

Supports incremental updates via a manifest file that tracks which
sessions have already been indexed.
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from base_rag_example import BaseRAGExample
from chunking import create_text_chunks

from claude_code_data.claude_code_reader import ClaudeCodeReader

# Keys from ClaudeCodeReader._base_metadata() to preserve through chunking
_CLAUDE_CODE_METADATA_KEYS = [
    "session_id",
    "project_name",
    "session_summary",
    "message_count",
    "turn_id",
]

# ---------------------------------------------------------------------------
# Manifest helpers
# ---------------------------------------------------------------------------

MANIFEST_FILENAME = "indexed_sessions.json"


def _load_manifest(index_dir: str) -> dict:
    path = Path(index_dir) / MANIFEST_FILENAME
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def _save_manifest(index_dir: str, manifest: dict) -> None:
    path = Path(index_dir) / MANIFEST_FILENAME
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")


def _file_mtime(path: Path) -> int:
    """Return mtime in milliseconds (matching sessions-index.json convention)."""
    try:
        return int(path.stat().st_mtime * 1000)
    except OSError:
        return 0


def _count_lines(path: Path) -> int:
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            return sum(1 for _ in f)
    except OSError:
        return 0


# ---------------------------------------------------------------------------
# ClaudeCodeRAG
# ---------------------------------------------------------------------------


class ClaudeCodeRAG(BaseRAGExample):
    """RAG example for Claude Code session data with incremental indexing."""

    def __init__(self):
        self.max_items_default = -1
        self.embedding_model_default = "bge-m3"
        super().__init__(
            name="Claude Code",
            description="Index and query Claude Code session transcripts with LEANN",
            default_index_name="claude_code_sessions_index",
        )
        # Override default index-dir to ~/.leann/indexes/claude-code-sessions
        default_index_dir = str(
            Path.home() / ".leann" / "indexes" / "claude-code-sessions"
        )
        for action in self.parser._actions:
            if hasattr(action, "option_strings") and "--index-dir" in action.option_strings:
                action.default = default_index_dir
                action.help = f"Directory to store the index (default: {default_index_dir})"
                break

    # ------------------------------------------------------------------
    # CLI arguments
    # ------------------------------------------------------------------

    def _add_specific_arguments(self, parser):
        grp = parser.add_argument_group("Claude Code Parameters")
        grp.add_argument(
            "--session-dirs",
            nargs="+",
            default=[str(Path.home() / ".claude" / "projects")],
            help="Directories containing Claude Code project folders (default: ~/.claude/projects)",
        )
        grp.add_argument(
            "--project-filter",
            type=str,
            default=None,
            help="Only index projects whose name contains this string",
        )
        grp.add_argument(
            "--granularity",
            type=str,
            default="turn",
            choices=["turn", "session", "message"],
            help="Document granularity (default: turn)",
        )
        grp.add_argument(
            "--include-tool-names",
            action="store_true",
            default=True,
            help="Include tool names in indexed text (default: True)",
        )
        grp.add_argument(
            "--no-tool-names",
            action="store_true",
            default=False,
            help="Disable tool name inclusion",
        )
        grp.add_argument(
            "--no-summaries",
            action="store_true",
            default=False,
            help="Do not index session summaries",
        )
        grp.add_argument(
            "--no-agents",
            action="store_true",
            default=False,
            help="Do not index subagent conversations",
        )
        grp.add_argument(
            "--chunk-size",
            type=int,
            default=512,
            help="Text chunk size (default: 512)",
        )
        grp.add_argument(
            "--chunk-overlap",
            type=int,
            default=128,
            help="Text chunk overlap (default: 128)",
        )
        grp.add_argument(
            "--max-text-per-turn",
            type=int,
            default=0,
            help="Max characters per turn (0 = unlimited, chunking handles it)",
        )

    # ------------------------------------------------------------------
    # Data loading (full)
    # ------------------------------------------------------------------

    async def load_data(self, args) -> list[dict[str, Any]]:
        """Load all session data and convert to text chunks."""
        include_tool = args.include_tool_names and not args.no_tool_names

        reader = ClaudeCodeReader(
            granularity=args.granularity,
            include_tool_names=include_tool,
            include_summaries=not args.no_summaries,
            include_agents=not args.no_agents,
            max_text_per_turn=args.max_text_per_turn,
        )

        documents = reader.load_data(
            base_dirs=args.session_dirs,
            max_count=args.max_items,
            include_metadata=True,
            project_filter=args.project_filter,
        )

        if not documents:
            print("No documents found!")
            return []

        print(f"Loaded {len(documents)} documents, creating text chunks...")
        chunks = create_text_chunks(
            documents,
            chunk_size=args.chunk_size,
            chunk_overlap=args.chunk_overlap,
            extra_metadata_keys=_CLAUDE_CODE_METADATA_KEYS,
        )
        print(f"Created {len(chunks)} text chunks")
        return chunks

    # ------------------------------------------------------------------
    # Incremental update
    # ------------------------------------------------------------------

    def _discover_session_files(self, args) -> dict[str, Path]:
        """Return dict mapping session_id -> JSONL path for all sessions."""
        sessions: dict[str, Path] = {}
        for base in args.session_dirs:
            base_path = Path(base)
            if not base_path.is_dir():
                continue
            for project_dir in sorted(base_path.iterdir()):
                if not project_dir.is_dir():
                    continue
                if args.project_filter:
                    name = ClaudeCodeReader._extract_project_name(project_dir.name)
                    if args.project_filter.lower() not in name.lower():
                        continue
                for jsonl in project_dir.glob("*.jsonl"):
                    sid = jsonl.stem
                    if sid not in sessions:
                        sessions[sid] = jsonl
        return sessions

    async def _incremental_load(self, args) -> tuple[list[dict[str, Any]], dict]:
        """Load only new/modified sessions. Returns (chunks, updated_manifest)."""
        manifest = _load_manifest(args.index_dir)

        # Check embedding model consistency
        if manifest.get("embedding_model") and manifest["embedding_model"] != args.embedding_model:
            print(
                f"Embedding model changed ({manifest['embedding_model']} -> {args.embedding_model}). "
                "Full rebuild required."
            )
            return [], manifest

        session_files = self._discover_session_files(args)
        indexed = manifest.get("sessions", {})

        new_sessions: dict[str, Path] = {}
        modified_sessions: dict[str, tuple[Path, int]] = {}  # sid -> (path, old_lines)

        for sid, path in session_files.items():
            mtime = _file_mtime(path)
            if sid not in indexed:
                new_sessions[sid] = path
            elif indexed[sid].get("mtime", 0) != mtime:
                old_lines = indexed[sid].get("lines_indexed", 0)
                modified_sessions[sid] = (path, old_lines)

        if not new_sessions and not modified_sessions:
            print("Index is up to date — no new or modified sessions.")
            return [], manifest

        print(
            f"Incremental update: {len(new_sessions)} new, "
            f"{len(modified_sessions)} modified sessions"
        )

        include_tool = args.include_tool_names and not args.no_tool_names
        reader = ClaudeCodeReader(
            granularity=args.granularity,
            include_tool_names=include_tool,
            include_summaries=not args.no_summaries,
            include_agents=not args.no_agents,
            max_text_per_turn=args.max_text_per_turn,
        )

        all_documents = []

        # New sessions: parse fully
        for sid, path in new_sessions.items():
            project_dir = path.parent
            project_name = ClaudeCodeReader._extract_project_name(project_dir.name)
            sessions_index = reader._load_sessions_index(project_dir)
            session_meta = sessions_index.get(sid, {})
            session_meta.setdefault("project_name", project_name)
            session_meta.setdefault("project_dir", str(project_dir))

            docs = reader._parse_session_file(path, session_meta)
            all_documents.extend(docs)

            # Agents
            if not args.no_agents:
                session_dir = project_dir / sid
                for agent_path in reader._discover_agent_files(session_dir):
                    all_documents.extend(reader._parse_agent_file(agent_path, session_meta))

            total_lines = _count_lines(path)
            indexed[sid] = {
                "mtime": _file_mtime(path),
                "lines_indexed": total_lines,
                "project": project_name,
            }

        # Modified sessions: parse only new lines
        for sid, (path, old_lines) in modified_sessions.items():
            project_dir = path.parent
            project_name = ClaudeCodeReader._extract_project_name(project_dir.name)
            sessions_index = reader._load_sessions_index(project_dir)
            session_meta = sessions_index.get(sid, {})
            session_meta.setdefault("project_name", project_name)
            session_meta.setdefault("project_dir", str(project_dir))

            # Read only lines after old_lines
            entries = []
            try:
                with open(path, encoding="utf-8", errors="replace") as f:
                    for i, line in enumerate(f):
                        if i < old_lines:
                            continue
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            entries.append(json.loads(line))
                        except json.JSONDecodeError:
                            continue
            except OSError:
                continue

            if entries:
                # Use internal methods to parse the new entries
                if reader.granularity == "turn":
                    docs = reader._build_turn_docs(entries, sid, session_meta, True)
                elif reader.granularity == "session":
                    doc = reader._build_session_doc(entries, sid, session_meta, True)
                    docs = [doc] if doc else []
                else:
                    docs = reader._build_message_docs(entries, sid, session_meta, True)
                all_documents.extend(docs)

            total_lines = _count_lines(path)
            indexed[sid] = {
                "mtime": _file_mtime(path),
                "lines_indexed": total_lines,
                "project": project_name,
            }

        if not all_documents:
            return [], manifest

        chunks = create_text_chunks(
            all_documents,
            chunk_size=args.chunk_size,
            chunk_overlap=args.chunk_overlap,
            extra_metadata_keys=_CLAUDE_CODE_METADATA_KEYS,
        )
        print(f"Incremental: {len(all_documents)} new documents -> {len(chunks)} chunks")

        manifest["sessions"] = indexed
        manifest["embedding_model"] = args.embedding_model
        manifest["build_timestamp"] = datetime.now(timezone.utc).isoformat()
        return chunks, manifest

    # ------------------------------------------------------------------
    # Overridden run() for incremental support
    # ------------------------------------------------------------------

    async def run(self):
        """Main entry point with incremental update support."""
        args = self.parser.parse_args()

        index_path = str(Path(args.index_dir) / f"{self.default_index_name}.leann")
        meta_file = Path(index_path + ".meta.json")
        index_exists = meta_file.exists()

        if args.force_rebuild or not index_exists:
            if index_exists:
                print("Force rebuilding index...")
            else:
                print("Building index for the first time...")

            texts = await self.load_data(args)
            if not texts:
                print("No data found to index!")
                return

            index_path = await self.build_index(args, texts)
            self._register_index(index_path)

            # Save manifest after full build
            session_files = self._discover_session_files(args)
            manifest = {
                "build_timestamp": datetime.now(timezone.utc).isoformat(),
                "embedding_model": args.embedding_model,
                "sessions": {},
            }
            for sid, path in session_files.items():
                project_dir = path.parent
                manifest["sessions"][sid] = {
                    "mtime": _file_mtime(path),
                    "lines_indexed": _count_lines(path),
                    "project": ClaudeCodeReader._extract_project_name(project_dir.name),
                }
            _save_manifest(args.index_dir, manifest)

        else:
            # Try incremental update
            chunks, manifest = await self._incremental_load(args)

            if chunks:
                try:
                    index_path = await self._update_index(args, chunks, index_path)
                    _save_manifest(args.index_dir, manifest)
                    print("Incremental update successful.")
                except Exception as e:
                    print(f"Warning: update_index() failed ({e}), falling back to full rebuild...")
                    texts = await self.load_data(args)
                    if texts:
                        index_path = await self.build_index(args, texts)
                        # Rebuild manifest
                        session_files = self._discover_session_files(args)
                        manifest = {
                            "build_timestamp": datetime.now(timezone.utc).isoformat(),
                            "embedding_model": args.embedding_model,
                            "sessions": {},
                        }
                        for sid, path in session_files.items():
                            project_dir = path.parent
                            manifest["sessions"][sid] = {
                                "mtime": _file_mtime(path),
                                "lines_indexed": _count_lines(path),
                                "project": ClaudeCodeReader._extract_project_name(
                                    project_dir.name
                                ),
                            }
                        _save_manifest(args.index_dir, manifest)
            else:
                print(f"Using existing index in {args.index_dir}")

        # Run query or interactive mode
        if args.query:
            await self.run_single_query(args, index_path, args.query)
        else:
            await self.run_interactive_chat(args, index_path)

    @staticmethod
    def _register_index(index_path: str) -> None:
        """Register the index in the global LEANN registry for MCP discovery."""
        try:
            from leann.registry import register_index
            register_index("claude-code-sessions", index_path, index_type="app")
        except Exception:
            pass  # Non-critical — index still works without registry

    async def _update_index(
        self, args, chunks: list[dict[str, Any]], index_path: str
    ) -> str:
        """Append new chunks to existing index using LeannBuilder.update_index()."""
        from leann.api import LeannBuilder

        try:
            from leann.settings import resolve_ollama_host
        except ImportError:
            import os

            def resolve_ollama_host(v):
                return v or os.getenv("LEANN_OLLAMA_HOST") or os.getenv("OLLAMA_HOST")

        embedding_options: dict[str, Any] = {}
        if args.embedding_mode == "ollama":
            embedding_options["host"] = resolve_ollama_host(args.embedding_host)

        builder = LeannBuilder(
            backend_name=args.backend_name,
            embedding_model=args.embedding_model,
            embedding_mode=args.embedding_mode,
            embedding_options=embedding_options or None,
            graph_degree=args.graph_degree,
            complexity=args.build_complexity,
            is_compact=False,
            is_recompute=False,
            num_threads=1,
        )

        # Read existing passage count to offset new IDs
        meta_path = Path(index_path + ".meta.json")
        existing_count = 0
        if meta_path.exists():
            try:
                meta = json.loads(meta_path.read_text())
                existing_count = meta.get("total_passages", 0)
            except (json.JSONDecodeError, OSError):
                pass
        # Fallback: count lines in passages file
        if existing_count == 0:
            passages_path = Path(index_path + ".passages.jsonl")
            if passages_path.exists():
                existing_count = _count_lines(passages_path)

        for i, item in enumerate(chunks):
            uid = str(existing_count + i)
            if isinstance(item, dict):
                meta = item.get("metadata") or {}
                meta["id"] = uid
                builder.add_text(item.get("text", ""), meta)
            else:
                builder.add_text(item, {"id": uid})

        print(f"Appending {len(chunks)} chunks to existing index...")
        builder.update_index(index_path)
        print("update_index() completed successfully.")
        return index_path


if __name__ == "__main__":
    import asyncio

    print("\n📋 Claude Code RAG")
    print("=" * 50)
    print("\nExample queries:")
    print("- 'Comment est configuré le thermostat ?'")
    print("- 'Show me how fuel consumption tracking works'")
    print("- 'Find discussions about dashboard configuration'")
    print()

    rag = ClaudeCodeRAG()
    asyncio.run(rag.run())
