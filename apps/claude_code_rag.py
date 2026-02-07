"""
Claude Code RAG — index and search Claude Code JSONL session transcripts.

Follows the BaseRAGExample pattern (like claude_rag.py, slack_rag.py).
Supports full rebuild and incremental updates via a session manifest.

Usage:
    # Full build
    uv run python -m apps.claude_code_rag --force-rebuild

    # Incremental update
    uv run python -m apps.claude_code_rag

    # Build + query
    uv run python -m apps.claude_code_rag --query "how does AST chunking work"

    # Filter by project
    uv run python -m apps.claude_code_rag --project-filter leann-fork
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
from leann.api import LeannBuilder
from leann.registry import register_index, register_project_directory

# Metadata keys to preserve through chunking
_EXTRA_METADATA_KEYS = [
    "session_id",
    "turn_id",
    "project_name",
    "git_branch",
    "timestamp",
    "entry_type",
    "is_subagent",
    "agent_file",
]

# Default index location
_DEFAULT_INDEX_DIR = str(Path.home() / ".leann" / "indexes" / "claude-code-sessions")


class ClaudeCodeRAG(BaseRAGExample):
    """RAG app for Claude Code JSONL session transcripts."""

    def __init__(self):
        self.max_items_default = -1
        self.embedding_model_default = "facebook/contriever"

        super().__init__(
            name="Claude Code Sessions",
            description="Index and search Claude Code conversation transcripts",
            default_index_name="claude-code-sessions",
        )

    def _create_parser(self):
        parser = super()._create_parser()
        # Override default index-dir to ~/.leann/indexes/claude-code-sessions
        for action in parser._actions:
            if hasattr(action, "dest") and action.dest == "index_dir":
                action.default = _DEFAULT_INDEX_DIR
                break
        return parser

    def _add_specific_arguments(self, parser):
        """Add Claude Code specific arguments."""
        cc_group = parser.add_argument_group("Claude Code Parameters")
        cc_group.add_argument(
            "--session-dirs",
            nargs="+",
            default=[str(Path.home() / ".claude" / "projects")],
            help="Directories containing Claude Code projects (default: ~/.claude/projects)",
        )
        cc_group.add_argument(
            "--project-filter",
            type=str,
            default=None,
            help="Only index projects whose name contains this string",
        )
        cc_group.add_argument(
            "--include-agents",
            action="store_true",
            default=True,
            help="Include subagent transcripts (default: True)",
        )
        cc_group.add_argument(
            "--no-agents",
            action="store_true",
            help="Exclude subagent transcripts",
        )
        cc_group.add_argument(
            "--exclude-session",
            nargs="*",
            default=[],
            help="Session IDs to exclude (e.g., the current session for hooks)",
        )
        cc_group.add_argument(
            "--chunk-size",
            type=int,
            default=512,
            help="Text chunk size in tokens (default: 512)",
        )
        cc_group.add_argument(
            "--chunk-overlap",
            type=int,
            default=128,
            help="Text chunk overlap in tokens (default: 128)",
        )
        cc_group.add_argument(
            "--no-header",
            action="store_true",
            help="Omit metadata header from passage text (metadata still in structured fields)",
        )

    # ------------------------------------------------------------------
    # Data loading
    # ------------------------------------------------------------------

    async def load_data(self, args) -> list[dict[str, Any]]:
        """Load Claude Code sessions and convert to text chunks."""
        include_agents = args.include_agents and not args.no_agents
        reader = ClaudeCodeReader(
            granularity="turn",
            include_agents=include_agents,
        )

        documents = reader.load_data(
            base_dirs=args.session_dirs,
            max_count=args.max_items,
            include_metadata=True,
            include_header=not args.no_header,
            project_filter=args.project_filter,
            exclude_sessions=set(args.exclude_session or []),
        )

        if not documents:
            return []

        print(f"Chunking {len(documents)} documents...")
        chunks = create_text_chunks(
            documents,
            chunk_size=args.chunk_size,
            chunk_overlap=args.chunk_overlap,
            extra_metadata_keys=_EXTRA_METADATA_KEYS,
        )
        print(f"Created {len(chunks)} text chunks")
        return chunks

    # ------------------------------------------------------------------
    # Manifest management
    # ------------------------------------------------------------------

    def _manifest_path(self, index_dir: str) -> Path:
        return Path(index_dir) / "indexed_sessions.json"

    def _load_manifest(self, index_dir: str) -> dict:
        path = self._manifest_path(index_dir)
        if path.exists():
            with open(path, encoding="utf-8") as f:
                return json.load(f)
        return {"sessions": {}}

    def _save_manifest(
        self,
        index_dir: str,
        session_infos: dict[str, dict],
        embedding_model: str,
    ):
        manifest = {
            "embedding_model": embedding_model,
            "build_timestamp": datetime.now(timezone.utc).isoformat(),
            "sessions": session_infos,
        }
        path = self._manifest_path(index_dir)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2)

    def _scan_current_sessions(
        self, base_dirs: list[str], project_filter: str | None = None
    ) -> dict[str, dict]:
        """Scan disk for all session files and their mtimes."""
        sessions: dict[str, dict] = {}
        reader = ClaudeCodeReader()
        projects = reader._discover_projects(base_dirs)

        if project_filter:
            projects = {
                k: v for k, v in projects.items() if project_filter.lower() in v["name"].lower()
            }

        for proj_dir, proj_info in projects.items():
            for jsonl_path in Path(proj_dir).glob("*.jsonl"):
                session_id = jsonl_path.stem
                if session_id.startswith("agent-"):
                    continue
                sessions[session_id] = {
                    "mtime": jsonl_path.stat().st_mtime,
                    "project": proj_info["name"],
                    "path": str(jsonl_path),
                }
        return sessions

    def _find_new_or_modified_sessions(
        self, manifest: dict, current: dict[str, dict]
    ) -> dict[str, dict]:
        """Find sessions not yet indexed or modified since last index."""
        indexed = manifest.get("sessions", {})
        new_sessions: dict[str, dict] = {}
        for sid, info in current.items():
            if sid not in indexed:
                new_sessions[sid] = info
            elif info["mtime"] > indexed[sid].get("mtime", 0):
                new_sessions[sid] = info
        return new_sessions

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def _register_index(self, index_dir: str):
        """Register the index so leann list / MCP can discover it."""
        index_path = str(Path(index_dir) / f"{self.default_index_name}.leann")
        register_index(self.default_index_name, index_path, index_type="app")
        register_project_directory(Path(index_dir))

    # ------------------------------------------------------------------
    # Incremental update
    # ------------------------------------------------------------------

    def _do_incremental_update(self, args, new_sessions: dict[str, dict]):
        """Load new sessions, chunk, embed, and append to existing index."""
        include_agents = args.include_agents and not args.no_agents
        reader = ClaudeCodeReader(
            granularity="turn",
            include_agents=include_agents,
        )

        # Only load new/modified session files
        new_session_ids = set(new_sessions.keys())
        all_session_ids = set(
            self._scan_current_sessions(args.session_dirs, args.project_filter).keys()
        )
        exclude = (all_session_ids - new_session_ids) | set(args.exclude_session or [])

        documents = reader.load_data(
            base_dirs=args.session_dirs,
            include_metadata=True,
            include_header=not args.no_header,
            project_filter=args.project_filter,
            exclude_sessions=exclude,
        )

        if not documents:
            print("No new documents to index.")
            return

        print(f"Chunking {len(documents)} new documents...")
        chunks = create_text_chunks(
            documents,
            chunk_size=args.chunk_size,
            chunk_overlap=args.chunk_overlap,
            extra_metadata_keys=_EXTRA_METADATA_KEYS,
        )

        if not chunks:
            print("No chunks produced.")
            return

        print(f"Appending {len(chunks)} chunks to index...")

        index_path = str(Path(args.index_dir) / f"{self.default_index_name}.leann")

        # Build a builder with same settings, add chunks, call update_index
        builder = LeannBuilder(
            backend_name=args.backend_name,
            embedding_model=args.embedding_model,
            embedding_mode=args.embedding_mode,
            graph_degree=args.graph_degree,
            complexity=args.build_complexity,
            is_compact=False,
            is_recompute=False,
            num_threads=1,
        )

        for i, chunk in enumerate(chunks):
            text = chunk.get("text", "")
            metadata = dict(chunk.get("metadata") or {})
            # Use a temporary unique ID prefix to avoid collision with
            # existing sequential IDs ("0","1",...). update_index() will
            # reassign proper IDs based on index.ntotal.
            metadata["id"] = f"_update_{i}"
            builder.add_text(text, metadata)

        builder.update_index(index_path)
        print(f"Index updated successfully ({len(chunks)} chunks added)")

    # ------------------------------------------------------------------
    # Main flow
    # ------------------------------------------------------------------

    async def run(self):
        args = self.parser.parse_args()
        index_dir = args.index_dir
        index_path = str(Path(index_dir) / f"{self.default_index_name}.leann")
        meta_path = f"{index_path}.meta.json"
        index_exists = Path(meta_path).exists()

        if not index_exists or args.force_rebuild:
            # Full build
            print(f"\n{'Rebuilding' if index_exists else 'Building'} index...")
            texts = await self.load_data(args)
            if not texts:
                print("No data found to index!")
                return

            # Force non-compact + no-recompute for fast search and incremental updates
            args.no_compact = True
            args.no_recompute = True

            index_path = await self.build_index(args, texts)
            self._register_index(index_dir)

            # Save manifest
            current_sessions = self._scan_current_sessions(args.session_dirs, args.project_filter)
            self._save_manifest(index_dir, current_sessions, args.embedding_model)
            print(f"Manifest saved ({len(current_sessions)} sessions tracked)")

        else:
            # Incremental update
            print(f"\nUsing existing index in {index_dir}")
            manifest = self._load_manifest(index_dir)
            current_sessions = self._scan_current_sessions(args.session_dirs, args.project_filter)
            new_sessions = self._find_new_or_modified_sessions(manifest, current_sessions)

            if new_sessions:
                print(f"Found {len(new_sessions)} new/modified sessions")
                self._do_incremental_update(args, new_sessions)
                # Update manifest with all current sessions
                all_sessions = {**manifest.get("sessions", {})}
                for sid, info in new_sessions.items():
                    all_sessions[sid] = {
                        "mtime": info["mtime"],
                        "project": info["project"],
                    }
                self._save_manifest(index_dir, all_sessions, args.embedding_model)
                self._register_index(index_dir)
            else:
                print("Index is up to date — no new sessions found.")

        # Query if requested
        if args.query:
            await self.run_single_query(args, index_path, args.query)


if __name__ == "__main__":
    import asyncio

    print("\nClaude Code Sessions RAG")
    print("=" * 50)
    print("\nIndexes Claude Code conversation transcripts (~/.claude/projects/)")
    print("for semantic search via CLI and MCP.\n")

    rag = ClaudeCodeRAG()
    asyncio.run(rag.run())
