# CLAUDE.md — LEANN Fork (Claude Code RAG)

Ce fork de LEANN implémente un système de mémoire long-terme pour Claude Code : indexation sémantique des sessions JSONL, recherche hybride via MCP, hooks automatiques, et skills Claude Code.

## Architecture du fork

### Pipeline d'indexation

```
Sessions JSONL → ClaudeCodeRAG → Ollama (qwen3-embedding:4b) → Index HNSW
~/.claude/projects/<dir>/*.jsonl    apps/claude_code_rag.py              ~/.leann/indexes/claude-code-sessions/
```

- **Mode** : `--no-recompute --no-compact` (embeddings stockés dans l'index, recherche 68× plus rapide)
- **Modèle** : `qwen3-embedding:4b` (4B params, 2560 dims, instruction-aware via `query_prompt_template`)
- **Chunks** : 512 tokens, overlap 128

### Fichiers clés du fork

| Fichier | Rôle |
|---|---|
| `apps/claude_code_rag.py` | RAG principal : chargement sessions, indexation incrémentale, mise à jour |
| `apps/base_rag_example.py` | Classe de base partagée par toutes les apps RAG |
| `scripts/leann-index-progress.py` | Script d'indexation avec progression (lancé par `/init-context`) |
| `scripts/leann-session-start.py` | Hook `SessionStart` : détecte le delta et suggère `/init-context` |
| `scripts/leann-extract-tasks.py` | Extraction de tâches depuis les sessions JSONL |
| `scripts/deploy.sh` | Déploiement : pipx, HNSW rebuild auto, skills, rules, hooks, MCP |
| `scripts/claude-skills/` | Skills Claude Code (`init-context`, `leann-search`) |
| `scripts/claude-rules/` | Règles Claude Code (`task-memory`, `leann-search`) |
| `.claude/settings.local.json` | Hook `SessionStart` → `~/.leann/hooks/session-start.sh` (par projet, gitignored) |

### Core LEANN (upstream)

| Fichier | Rôle |
|---|---|
| `packages/leann-core/src/leann/api.py` | `LeannBuilder`, `LeannSearcher`, `LeannChat` |
| `packages/leann-core/src/leann/embedding_compute.py` | Calcul d'embeddings (Ollama, sentence-transformers, OpenAI) |
| `packages/leann-core/src/leann/mcp.py` | Serveur MCP (agnostique du modèle d'embedding) |
| `packages/leann-backend-hnsw/` | Backend FAISS HNSW |

## Commandes courantes

```bash
# Indexation manuelle (avec progression)
uv run python scripts/leann-index-progress.py

# Déploiement (pipx, HNSW rebuild, skills, rules, hooks, MCP)
bash scripts/deploy.sh --check   # vérifier l'état (inclut freshness .so)
bash scripts/deploy.sh           # quick: rebuild HNSW si .venv plus récent
bash scripts/deploy.sh --full    # réinstallation complète (pipx + inject)

# Tests
uv run pytest -m "not slow and not openai" -x

# Lint
ruff format && ruff check --fix
```

## Hooks

Le hook `SessionStart` est configuré par projet dans `.claude/settings.local.json` (gitignored) :
- **Déclencheur** : démarrage de chaque session Claude Code
- **Script** : `~/.leann/hooks/session-start.sh` → `scripts/leann-session-start.py` (via `uv run`)
- **Rôle** : report delta uniquement (sessions non indexées), suggère `/init-context`
- **Déployé par** : `deploy.sh` (`install_hooks`) ou `scripts/leann-whitelist.py add`

## Configuration

- **Ollama** : Flash Attention configurée dans `/etc/systemd/system/ollama.service.d/override.conf`
- **Whitelist projets** : `~/.leann/whitelist.json`
- **Index** : `~/.leann/indexes/claude-code-sessions/`
- **Manifest** : `indexed_sessions.json` (tracking mtime + lines par session)
- **MCP server** : `leann_mcp` installé via pipx (editable)
- **Hooks** : `~/.leann/hooks/session-start.sh` (partagé entre projets)

## Index LEANN

Structure d'un index :
- `<name>.meta.json` : métadonnées (modèle, dimensions, `embedding_options` dont `query_prompt_template`)
- `<name>.passages.jsonl` : chunks texte avec métadonnées
- `<name>.passages.idx` : offset map pour lookup rapide
- `<name>.index` : index vectoriel HNSW

## Python

Requiert Python 3.10+ (syntaxe union PEP 604 `X | Y`).
