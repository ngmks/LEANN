#!/usr/bin/env python3

import json
import subprocess
import sys


def handle_request(request):
    if request.get("method") == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": request.get("id"),
            "result": {
                "capabilities": {"tools": {}},
                "protocolVersion": "2024-11-05",
                "serverInfo": {"name": "leann-mcp", "version": "1.0.0"},
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
                        "description": """🔍 Search your LEANN indexes using natural language.

🎯 **Works with any indexed content**: code, Claude Code sessions, chat exports, documents...

💡 **Tips**:
- Use 'leann_list' first to see available indexes
- Use 'show_metadata: true' to discover filterable fields
- Use 'metadata_filter' to narrow results by project, branch, date, etc.""",
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
                                "metadata_filter": {
                                    "type": "object",
                                    "description": (
                                        "Filter results by metadata fields. "
                                        "Use show_metadata=true first to discover available fields for an index. "
                                        'Format: {"field": {"op": value}}. '
                                        "Ops: ==, !=, <, >, in, not_in, contains, starts_with. "
                                        "All conditions are ANDed. "
                                        'Ex: {"project_name": {"==": "my-app"}, '
                                        '"git_branch": {"in": ["main", "dev"]}}'
                                    ),
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
                if args.get("metadata_filter"):
                    cmd.append(f"--metadata-filter={json.dumps(args['metadata_filter'])}")
                result = subprocess.run(cmd, capture_output=True, text=True)

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
