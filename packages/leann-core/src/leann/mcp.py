#!/usr/bin/env python3

import json
import subprocess
import sys

from leann.api import LeannSearcher
from leann.registry import list_registered_indexes

_searcher_cache: dict[str, LeannSearcher] = {}


def _resolve_index_path(index_name: str) -> str:
    """Resolve an index name to its filesystem path via the global registry."""
    indexes = list_registered_indexes(validate=True)
    for idx in indexes:
        if idx["name"] == index_name:
            return idx["path"]
    raise ValueError(f"Index '{index_name}' not found in registry. Use leann_list to see available indexes.")


def _do_full_search(args: dict) -> str:
    """Perform a full search using the Python API directly, returning complete text and metadata."""
    index_name = args.get("index_name", "")
    query = args.get("query", "")
    top_k = args.get("top_k", 5)
    complexity = args.get("complexity", 32)
    show_metadata = args.get("show_metadata", True)
    gemma = args.get("gemma", 0.5)

    if not index_name or not query:
        return "Error: Both index_name and query are required"

    index_path = _resolve_index_path(index_name)

    # Reuse cached searcher or create a new one
    if index_path not in _searcher_cache:
        _searcher_cache[index_path] = LeannSearcher(index_path, enable_warmup=True)

    searcher = _searcher_cache[index_path]
    results = searcher.search(query, top_k=top_k, complexity=complexity, gemma=gemma)

    if not results:
        return f"No results found for '{query}'."

    lines = [f"Search results for '{query}' (top {len(results)}):\n"]
    for i, r in enumerate(results, 1):
        lines.append(f"{i}. Score: {r.score:.3f}")
        if show_metadata and r.metadata:
            meta_parts = []
            for k, v in r.metadata.items():
                if k == "id":
                    continue
                meta_parts.append(f"{k}: {v}")
            if meta_parts:
                lines.append(f"   [Metadata]")
                lines.append(f"   {' | '.join(meta_parts)}")
        lines.append(f"   [Text]")
        lines.append(f"   {r.text}")
        lines.append("")

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
                    "Always prefer 'leann_full_search' over 'leann_search' — it returns complete, "
                    "non-truncated text with full metadata. "
                    "Key parameter: 'gemma' controls hybrid search — use 0.5 (default) for short/keyword "
                    "queries, 1.0 for long descriptive questions, 0.0 for exact keyword matching. "
                    "Always set show_metadata=true. Use 'leann_list' first to discover available indexes."
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
                        "description": """🔍 Search code using natural language - like having a coding assistant who knows your entire codebase!

🎯 **Perfect for**:
- "How does authentication work?" → finds auth-related code
- "Error handling patterns" → locates try-catch blocks and error logic
- "Database connection setup" → finds DB initialization code
- "API endpoint definitions" → locates route handlers
- "Configuration management" → finds config files and usage

💡 **Pro tip**: Use this before making any changes to understand existing patterns and conventions.""",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "index_name": {
                                    "type": "string",
                                    "description": "Name of the LEANN index to search. Use 'leann_list' first to see available indexes.",
                                },
                                "query": {
                                    "type": "string",
                                    "description": "Search query - can be natural language (e.g., 'how to handle errors') or technical terms (e.g., 'async function definition')",
                                },
                                "top_k": {
                                    "type": "integer",
                                    "default": 5,
                                    "minimum": 1,
                                    "maximum": 20,
                                    "description": "Number of search results to return. Use 5-10 for focused results, 15-20 for comprehensive exploration.",
                                },
                                "complexity": {
                                    "type": "integer",
                                    "default": 32,
                                    "minimum": 16,
                                    "maximum": 128,
                                    "description": "Search complexity level. Use 16-32 for fast searches (recommended), 64+ for higher precision when needed.",
                                },
                                "show_metadata": {
                                    "type": "boolean",
                                    "default": False,
                                    "description": "Include file paths and metadata in search results. Useful for understanding which files contain the results.",
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
                    {
                        "name": "leann_full_search",
                        "description": """🔍 **PREFERRED over leann_search** — Full-text semantic search with COMPLETE results (no truncation).

Returns the full content of each matching chunk along with all metadata. Always use this instead of leann_search unless you specifically need truncated previews.

⚙️ **How to tune `gemma` (hybrid search weight)**:
- User asks with short/vague keywords (e.g., "blague", "error handling") → use gemma=0.5 (hybrid: combines keyword matching + semantic)
- User asks a descriptive question (e.g., "how does the authentication flow work?") → use gemma=1.0 (pure semantic works well for longer queries)
- User wants exact phrase matching (e.g., "find where we use TODO") → use gemma=0.0 (pure keyword/BM25)
- When in doubt, use gemma=0.5 — it works well for most queries.

💡 **Tips**:
- Always set show_metadata=true so you can tell the user where results come from.
- For broad exploration, use top_k=10. For focused answers, top_k=3-5.
- If results seem off-topic, try lowering gemma (adds keyword matching) or rephrasing the query with more specific terms.""",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "index_name": {
                                    "type": "string",
                                    "description": "Name of the LEANN index to search. Use 'leann_list' first to see available indexes.",
                                },
                                "query": {
                                    "type": "string",
                                    "description": "Search query — natural language or technical terms. Longer, more descriptive queries give better semantic results. For short keyword queries, lower gemma to add keyword matching.",
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
                                    "default": True,
                                    "description": "Show metadata (project, file path, source) for each result. Recommended: always true.",
                                },
                                "gemma": {
                                    "type": "number",
                                    "default": 0.5,
                                    "minimum": 0.0,
                                    "maximum": 1.0,
                                    "description": "Hybrid search weight: 1.0 = pure semantic/vector, 0.0 = pure keyword/BM25, 0.5 = balanced hybrid (recommended default). Use 0.5 for short queries, 1.0 for long descriptive questions, 0.0 for exact keyword matching.",
                                },
                            },
                            "required": ["index_name", "query"],
                        },
                    },
                ]
            },
        }

    elif request.get("method") == "tools/call":
        tool_name = request["params"]["name"]
        args = request["params"].get("arguments", {})

        try:
            if tool_name == "leann_search":
                # Validate required parameters
                if not args.get("index_name") or not args.get("query"):
                    return {
                        "jsonrpc": "2.0",
                        "id": request.get("id"),
                        "result": {
                            "content": [
                                {
                                    "type": "text",
                                    "text": "Error: Both index_name and query are required",
                                }
                            ]
                        },
                    }

                # Build simplified command with non-interactive flag for MCP compatibility
                cmd = [
                    "leann",
                    "search",
                    args["index_name"],
                    args["query"],
                    f"--top-k={args.get('top_k', 5)}",
                    f"--complexity={args.get('complexity', 32)}",
                    "--non-interactive",
                ]
                if args.get("show_metadata", False):
                    cmd.append("--show-metadata")
                result = subprocess.run(cmd, capture_output=True, text=True)

            elif tool_name == "leann_full_search":
                text = _do_full_search(args)
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
