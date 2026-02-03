# LEANN Tests

This directory contains automated tests for the LEANN project using pytest.

## Setup

### Install all dependencies:
```bash
# Full install with all backends and test tools
uv sync --extra diskann --group test
```

### Verify key imports:
```bash
uv run python -c "import leann; import leann_backend_hnsw; import leann_backend_diskann; print('OK')"
```

## Test Files

### Core & Backend

| File | Tests | Description |
|------|-------|-------------|
| `test_basic.py` | 3 | Import checks, C++ extensions, basic build/search (HNSW + DiskANN) |
| `test_ci_minimal.py` | 4 | Minimal CI tests — no model loading or heavy memory usage |
| `test_readme_examples.py` | 5 | README code examples work correctly (parametrized HNSW + DiskANN) |
| `test_document_rag.py` | 5 | Document RAG with contriever/OpenAI embeddings |
| `test_astchunk_integration.py` | 25 | AST-aware code chunking integration with LEANN |

### Search & Filtering

| File | Tests | Description |
|------|-------|-------------|
| `test_hybrid_search.py` | 7 | Hybrid search (vector + BM25 via `gemma` parameter) |
| `test_metadata_filtering.py` | 26 | `MetadataFilterEngine` — all 13 operators, `PassageManager` integration |
| `test_warmup.py` | 10 | Warmup functionality for reducing search latency |

### CLI

| File | Tests | Description |
|------|-------|-------------|
| `test_cli_ask.py` | 1 | `leann ask` command |
| `test_cli_list_performance.py` | 14 | `leann list` — `_find_meta_files_limited` performance |
| `test_cli_prompt_template.py` | 11 | `--embedding-prompt-template` CLI argument |
| `test_cli_verbosity.py` | 11 | CLI verbosity options and C++ output suppression |

### Embeddings & Prompt Templates

| File | Tests | Description |
|------|-------|-------------|
| `test_embedding_prompt_template.py` | 7 | Prompt template prepending for OpenAI embeddings |
| `test_embedding_server_manager.py` | 1 | Embedding server lifecycle management |
| `test_prompt_template_persistence.py` | 13 | Prompt template metadata persistence and reuse across sessions |
| `test_token_truncation.py` | 24 | Token-aware truncation for embedding input |
| `test_lmstudio_bridge.py` | 11 | LM Studio TypeScript SDK bridge for context length detection |
| `test_prompt_template_e2e.py` | 10 | End-to-end with live services (LM Studio, Ollama). **Requires `@pytest.mark.integration`** |

### MCP

| File | Tests | Description |
|------|-------|-------------|
| `test_mcp_standalone.py` | 4 | MCP reader unit tests (Slack, Twitter) — no LEANN core needed |
| `test_mcp_integration.py` | 7 | MCP reader + RAG integration (Slack, Twitter) |

### Claude Code Sessions

| File | Tests | Description |
|------|-------|-------------|
| `test_claude_code_rag.py` | 20 | `ClaudeCodeReader` parsing + `ClaudeCodeRAG` pipeline |

Covers: turn/session/message granularity, agent subprocesses, summary indexing, deduplication, project name extraction, JSON malformé, incremental update, end-to-end build+search.

Imports `apps/claude_code_data/` via `sys.path` — no extra install needed beyond `uv sync`.

### DiskANN

| File | Tests | Description |
|------|-------|-------------|
| `test_diskann_partition.py` | 5 | Graph partitioning, medoid generation, partition search. **Skipped in CI** |

### Other

| File | Tests | Description |
|------|-------|-------------|
| `test_sync.py` | 5 | Synchronization utilities |

## Running Tests

### All tests (excluding known CI-incompatible ones):
```bash
uv run pytest tests/
```

### Skip slow or service-dependent tests:
```bash
# Skip slow tests
uv run pytest tests/ -m "not slow"

# Skip tests requiring OpenAI API key
uv run pytest tests/ -m "not openai"

# Skip integration tests (require LM Studio / Ollama running)
uv run pytest tests/ -m "not integration"
```

### Run by category:
```bash
# Claude Code session tests only
uv run pytest tests/test_claude_code_rag.py

# Metadata filtering tests only
uv run pytest tests/test_metadata_filtering.py

# All CLI tests
uv run pytest tests/ -k "cli"

# All MCP tests
uv run pytest tests/ -k "mcp"

# Specific backend
uv run pytest tests/ -k "hnsw"
uv run pytest tests/ -k "diskann"
```

### With coverage:
```bash
uv run pytest tests/ --cov=leann --cov-report=html
```

### In parallel:
```bash
uv run pytest tests/ -n auto
```

## Test Markers

| Marker | Meaning |
|--------|---------|
| `slow` | Long-running tests (deselect with `-m "not slow"`) |
| `openai` | Requires `OPENAI_API_KEY` env var |
| `integration` | Requires live services (LM Studio, Ollama) |

## Integration Test Prerequisites

| Service | URL | Required for |
|---------|-----|-------------|
| LM Studio | `http://localhost:1234` | `test_prompt_template_e2e.py` |
| Ollama | `http://localhost:11434` | Token limit detection, embeddings |
| Node.js + @lmstudio/sdk | — | `test_lmstudio_bridge.py` (SDK bridge) |

Tests gracefully skip if services are unavailable.

## Known Issues

- DiskANN partition tests are skipped in CI due to hardware requirements
- OpenAI tests skip automatically if no API key is set
- `test_hybrid_search.py` skips in CI to avoid MPS memory issues
- Integration tests may fail behind a proxy (`unset ALL_PROXY all_proxy`)
