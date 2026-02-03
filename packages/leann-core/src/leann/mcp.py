#!/usr/bin/env python3

import json
import subprocess
import sys

from leann.api import LeannSearcher
from leann.registry import list_registered_indexes

_searcher_cache: dict[str, LeannSearcher] = {}
_turn_index_cache: dict[str, dict[str, list[str]]] = {}  # index_path -> {turn_id -> [texts]}
_PROJECT_FILTER_OVERFETCH = 4


def _resolve_index_path(index_name: str) -> str:
    """Resolve an index name to its filesystem path via the global registry."""
    indexes = list_registered_indexes(validate=True)
    for idx in indexes:
        if idx["name"] == index_name:
            return idx["path"]
    raise ValueError(f"Index '{index_name}' not found in registry. Use leann_list to see available indexes.")


def _build_turn_index(index_path: str) -> dict[str, list[str]]:
    """Build a turn_id -> [texts] lookup from the passages file (cached)."""
    if index_path in _turn_index_cache:
        return _turn_index_cache[index_path]

    from pathlib import Path

    passages_path = Path(str(index_path) + ".passages.jsonl")
    turn_map: dict[str, list[str]] = {}
    try:
        with open(passages_path, encoding="utf-8") as f:
            for line in f:
                p = json.loads(line)
                turn_id = p.get("metadata", {}).get("turn_id", "")
                if turn_id:
                    turn_map.setdefault(turn_id, []).append(p["text"])
    except (OSError, json.JSONDecodeError):
        pass

    _turn_index_cache[index_path] = turn_map
    return turn_map


def _do_search(args: dict) -> str:
    """Perform a search using the Python API directly, returning text and optional metadata."""
    index_name = args.get("index_name", "")
    query = args.get("query", "")
    top_k = args.get("top_k", 5)
    complexity = args.get("complexity", 32)
    show_metadata = args.get("show_metadata", False)
    gemma = args.get("gemma", 0.5)
    expand_turns = args.get("expand_turns", False)
    project = args.get("project", "")

    if not index_name or not query:
        return "Error: Both index_name and query are required"

    index_path = _resolve_index_path(index_name)

    # Reuse cached searcher or create a new one
    if index_path not in _searcher_cache:
        _searcher_cache[index_path] = LeannSearcher(index_path, enable_warmup=True)

    searcher = _searcher_cache[index_path]

    # Over-fetch when project filter is active (metadata filtering is post-search)
    metadata_filters = None
    search_top_k = top_k
    if project:
        metadata_filters = {"project_name": {"contains": project}}
        search_top_k = min(top_k * _PROJECT_FILTER_OVERFETCH, 80)

    results = searcher.search(
        query, top_k=search_top_k, complexity=complexity, gemma=gemma,
        metadata_filters=metadata_filters,
    )

    if not results:
        if project:
            return f"No results found for '{query}' in project '{project}'."
        return f"No results found for '{query}'."

    # Build turn index only when needed
    turn_map = _build_turn_index(index_path) if expand_turns else {}

    lines = [""]  # placeholder for header, filled after counting
    seen_turns: set[str] = set()
    result_count = 0
    for r in results:
        if result_count >= top_k:
            break

        turn_id = r.metadata.get("turn_id", "") if r.metadata else ""

        # When expanding, skip duplicate turns (multiple chunks from same turn)
        if expand_turns and turn_id:
            if turn_id in seen_turns:
                continue
            seen_turns.add(turn_id)

        result_count += 1
        lines.append(f"{result_count}. Score: {r.score:.3f}")
        if show_metadata and r.metadata:
            meta_parts = []
            for k, v in r.metadata.items():
                if k == "id":
                    continue
                meta_parts.append(f"{k}: {v}")
            if meta_parts:
                lines.append("   [Metadata]")
                lines.append(f"   {' | '.join(meta_parts)}")

        if expand_turns and turn_id and turn_id in turn_map:
            lines.append("   [Full Turn]")
            lines.append(f"   {''.join(turn_map[turn_id])}")
        else:
            lines.append("   [Text]")
            lines.append(f"   {r.text}")
        lines.append("")

    header = f"Search results for '{query}'"
    if project:
        header += f" (project: '{project}')"
    header += f" (top {result_count}):\n"
    lines[0] = header

    return "\n".join(lines)


def handle_request(request):
    if request.get("method") == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": request.get("id"),
            "result": {
                "capabilities": {"tools": {}},
                "protocolVersion": "2024-11-05",
                "serverInfo": {"name": "leann-mcp", "version": "1.0.0"},
                "instructions": (
                    "LEANN is a semantic search engine over indexed codebases and session history. "
                    "Key parameter: 'gemma' controls hybrid search — use 0.5 (default) for short/keyword "
                    "queries, 1.0 for long descriptive questions, 0.0 for exact keyword matching. "
                    "Always set show_metadata=true. Use 'leann_list' first to discover available indexes. "
                    "Use expand_turns=true on session indexes to get full conversation turns instead of chunks. "
                    "Use 'project' to filter results by project name (substring match)."
                ),
            },
        }

    elif request.get("method") == "tools/list":
        return {
            "jsonrpc": "2.0",
            "id": request.get("id"),
            "result": {
                "tools": [
                    {
                        "name": "leann_search",
                        "description": """🔍 Semantic search with full results (no truncation). Supports hybrid search via `gemma` and full turn expansion via `expand_turns`.

⚙️ **`gemma` — hybrid search weight**:
- Short/vague keywords → gemma=0.5 (hybrid, default)
- Descriptive question → gemma=1.0 (pure semantic)
- Exact phrase matching → gemma=0.0 (pure keyword/BM25)

🔄 **`expand_turns`** — set to true on session indexes (e.g. claude-code-sessions) to return the full conversation turn instead of just the matched chunk. Deduplicates results from the same turn.

🏷️ **`project`** — filter by project name (substring match). Use show_metadata=true to discover project names.

💡 **Tips**:
- Set show_metadata=true to see where results come from (project, session, turn_id).
- For broad exploration, use top_k=10. For focused answers, top_k=3-5.""",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "index_name": {
                                    "type": "string",
                                    "description": "Name of the LEANN index to search. Use 'leann_list' first to see available indexes.",
                                },
                                "query": {
                                    "type": "string",
                                    "description": "Search query — natural language or technical terms. Longer, more descriptive queries give better semantic results.",
                                },
                                "top_k": {
                                    "type": "integer",
                                    "default": 5,
                                    "minimum": 1,
                                    "maximum": 20,
                                    "description": "Number of results. Use 3-5 for focused answers, 10-15 for broad exploration.",
                                },
                                "complexity": {
                                    "type": "integer",
                                    "default": 32,
                                    "minimum": 16,
                                    "maximum": 128,
                                    "description": "Search precision. 32 is fast and good enough for most queries. Use 64+ only when you need maximum recall.",
                                },
                                "show_metadata": {
                                    "type": "boolean",
                                    "default": False,
                                    "description": "Include metadata (project, file path, source) for each result.",
                                },
                                "gemma": {
                                    "type": "number",
                                    "default": 0.5,
                                    "minimum": 0.0,
                                    "maximum": 1.0,
                                    "description": "Hybrid search weight: 1.0 = pure semantic/vector, 0.0 = pure keyword/BM25, 0.5 = balanced hybrid (recommended default).",
                                },
                                "expand_turns": {
                                    "type": "boolean",
                                    "default": False,
                                    "description": "When true, return the full conversation turn instead of just the matched chunk. Only works on indexes with turn_id metadata (e.g. claude-code-sessions).",
                                },
                                "project": {
                                    "type": "string",
                                    "description": "Filter results to a specific project (substring match on project_name). Use show_metadata=true to discover available project names.",
                                },
                            },
                            "required": ["index_name", "query"],
                        },
                    },
                    {
                        "name": "leann_list",
                        "description": "📋 Show all your indexed codebases - your personal code library! Use this to see what's available for search.",
                        "inputSchema": {"type": "object", "properties": {}},
                    },
                ]
            },
        }

    elif request.get("method") == "tools/call":
        tool_name = request["params"]["name"]
        args = request["params"].get("arguments", {})

        try:
            if tool_name == "leann_search":
                text = _do_search(args)
                return {
                    "jsonrpc": "2.0",
                    "id": request.get("id"),
                    "result": {
                        "content": [{"type": "text", "text": text}]
                    },
                }

            elif tool_name == "leann_list":
                result = subprocess.run(["leann", "list"], capture_output=True, text=True)

            return {
                "jsonrpc": "2.0",
                "id": request.get("id"),
                "result": {
                    "content": [
                        {
                            "type": "text",
                            "text": result.stdout
                            if result.returncode == 0
                            else f"Error: {result.stderr}",
                        }
                    ]
                },
            }

        except Exception as e:
            return {
                "jsonrpc": "2.0",
                "id": request.get("id"),
                "error": {"code": -1, "message": str(e)},
            }


def main():
    for line in sys.stdin:
        try:
            request = json.loads(line.strip())
            response = handle_request(request)
            if response:
                print(json.dumps(response))
                sys.stdout.flush()
        except Exception as e:
            error_response = {
                "jsonrpc": "2.0",
                "id": None,
                "error": {"code": -1, "message": str(e)},
            }
            print(json.dumps(error_response))
            sys.stdout.flush()


if __name__ == "__main__":
    main()
