# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Fork Objective

This is a fork of [LEANN](https://github.com/yichuan-w/LEANN). The goal of this branch (`add-claude-code-jsonl-capability-to-claude-rag`) is to **extend the existing Claude RAG app to support Claude Code session files (JSONL format)**.

### Context

LEANN upstream already provides `apps/claude_rag.py` which indexes **Claude.ai web export** data (JSON files exported manually). Claude Code stores session transcripts locally as JSONL files in `~/.claude/projects/<encoded-dir>/*.jsonl`. Each line is a JSON object representing a conversation turn (user message, assistant response, tool call, etc.).

This branch adds the ability to index and search these JSONL session files, enabling semantic search across Claude Code conversation history.

### Key existing files to build upon

- `apps/claude_rag.py` → existing Claude RAG app (JSON exports) — pattern to follow or extend
- `apps/claude_data/claude_reader.py` → reader for Claude.ai JSON exports (extends `llama_index.BaseReader`)
- `apps/base_rag_example.py` → base class all RAG apps inherit from (`BaseRAGExample`)
- `apps/chunking/` → text chunking utilities shared across RAG apps
- `packages/leann-mcp/` → MCP server for Claude Code integration (currently only a README)


## Build & Development Commands

```bash
# Development setup (from source)
git submodule update --init --recursive

# Ubuntu/Debian
sudo apt-get install libomp-dev libboost-all-dev protobuf-compiler \
    libabsl-dev libmkl-full-dev libaio-dev libzmq3-dev
uv sync --extra diskann

# Install lint and test tools
uv sync --group lint --group test
```

## Testing

```bash
uv run pytest                          # All tests
uv run pytest tests/test_basic.py      # Single file
uv run pytest -m "not slow"            # Skip slow tests
uv run pytest -m "not openai"          # Skip OpenAI-dependent tests
uv run pytest --cov=leann              # With coverage
```

Test markers: `slow`, `openai`, `integration`

## Code Quality

```bash
uv run ruff format                     # Format code
uv run ruff check --fix                # Lint with auto-fix
uv run pre-commit run --all-files      # Run all pre-commit hooks
```

Note: `ruff` is not on the global PATH — always use `uv run ruff`.

## Architecture

### Core API Layer (`packages/leann-core/src/leann/`)

- `api.py`: Main APIs — `LeannBuilder`, `LeannSearcher`, `LeannChat`
- `embedding_compute.py`: Embedding computation (sentence-transformers, MLX, OpenAI, Ollama)
- `registry.py`: Backend auto-discovery and global index registry (`~/.leann/indexes.json`)
- `cli.py`: CLI (`leann build`, `leann search`, `leann ask`, `leann list`)
- `mcp.py`: MCP protocol support

### Backend Layer (`packages/`)

- `leann-backend-hnsw/`: Default backend using FAISS HNSW (includes C++ in `third_party/faiss`)
- `leann-backend-diskann/`: DiskANN backend for larger-than-memory datasets
- `leann-mcp/`: MCP server entry point for Claude Code integration

Backends are auto-discovered via `leann-backend-*` naming convention.

### RAG Apps (`apps/`)

Each RAG app follows the `BaseRAGExample` pattern:
1. Subclass `BaseRAGExample` (provides CLI args, build/search/chat flow)
2. Implement `load_data(args)` → returns list of text chunks with metadata
3. Use a `*Reader` class (extending `llama_index.BaseReader`) for data ingestion

### Index Structure

A LEANN index consists of:
- `<name>.meta.json`: Metadata (backend, embedding model, dimensions)
- `<name>.passages.jsonl`: Raw text chunks with metadata
- `<name>.passages.idx`: Offset map for fast passage lookup
- `<name>.index`: Backend-specific vector index

### Claude Code JSONL Session Format

Sessions are stored in `~/.claude/projects/<encoded-dir>/*.jsonl`. Each line is a JSON object with fields like:
- `type`: "user" | "assistant"
- `message.role`, `message.content`: the conversation content
- `sessionId`, `timestamp`, `cwd`, `version`
- `gitBranch`: branch active during the session

### Threading

LEANN sets `OMP_NUM_THREADS=1` and related env vars in `__init__.py` to prevent FAISS/ZMQ hangs. Do not override these.

## Python Version

Requires Python 3.10+ (uses PEP 604 union syntax `X | Y`).
