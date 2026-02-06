#!/usr/bin/env python3
"""
LEANN incremental indexation with progress output.

Launched by Claude via Bash when the user accepts indexation of a large delta.
Uses ClaudeCodeRAG._incremental_load() + _update_index() under the hood.

Usage (from LEANN_ROOT):
    uv run python scripts/leann-index-progress.py
"""

from __future__ import annotations

import asyncio
import fcntl
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

LOCKFILE_PATH = Path.home() / ".leann" / "indexing.lock"

# Make apps/ importable
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "apps"))


def _warmup_ollama(
    host: str = "http://localhost:11434", model: str = "qwen3-embedding:4b", rounds: int = 5
) -> bool:
    """
    Warm up Ollama embedding model to avoid cold start errors.

    Sends a few embedding requests to stabilize the GPU/CUDA kernels
    before the main indexation starts.
    """
    print(f"[LEANN] Warm-up Ollama ({model})...", end=" ", flush=True)

    # Sample texts of varying sizes to warm up different code paths
    warmup_texts = [
        "Hello world",
        "This is a test sentence for warming up the embedding model.",
        "Claude Code is an AI assistant that helps with software development tasks. " * 3,
    ]

    success_count = 0
    for i in range(rounds):
        try:
            response = requests.post(
                f"{host}/api/embed",
                json={"model": model, "input": warmup_texts},
                timeout=30,
            )
            if response.status_code == 200:
                success_count += 1
            else:
                print("⚠", end="", flush=True)
        except Exception:
            print("✗", end="", flush=True)

    if success_count >= rounds - 1:  # Allow 1 failure
        print(f"✓ ({success_count}/{rounds})")
        return True
    else:
        print(f"⚠ ({success_count}/{rounds} - continuing anyway)")
        return False


def _build_full_manifest(rag, args) -> dict:
    """Build and save a full manifest after a complete index build."""
    from claude_code_data.claude_code_reader import ClaudeCodeReader
    from claude_code_rag import _count_lines, _file_mtime, _save_manifest

    session_files = rag._discover_session_files(args)
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
    return manifest


def main() -> None:
    # Acquire indexation lock (non-blocking — skip if another session is indexing)
    LOCKFILE_PATH.parent.mkdir(parents=True, exist_ok=True)
    lock_fd = open(LOCKFILE_PATH, "w")
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        print("[LEANN] Indexation déjà en cours par une autre session.")
        lock_fd.close()
        return

    try:
        _run_indexation()
    finally:
        fcntl.flock(lock_fd, fcntl.LOCK_UN)
        lock_fd.close()


def _run_indexation() -> None:
    print("[LEANN] Démarrage de l'indexation incrémentale...")

    from claude_code_rag import ClaudeCodeRAG, _save_manifest

    rag = ClaudeCodeRAG()
    args = rag.parser.parse_args(
        [
            "--whitelist-file",
            str(Path.home() / ".leann" / "whitelist.json"),
            "--embedding-mode",
            "ollama",
            "--embedding-model",
            "qwen3-embedding:4b",
            "--no-compact",
            "--no-recompute",
        ]
    )

    # Warm up Ollama to avoid cold start errors
    _warmup_ollama(model=args.embedding_model)

    index_path = str(Path(args.index_dir) / f"{rag.default_index_name}.leann")
    meta_file = Path(index_path + ".meta.json")

    if not meta_file.exists():
        print("[LEANN] Aucun index existant. Lancement d'un build complet...")
        t0 = time.monotonic()

        print("[LEANN] Phase 1/3 — Chargement des sessions...", flush=True)
        texts = asyncio.run(rag.load_data(args))
        if not texts:
            print("[LEANN] Aucune donnée trouvée !")
            return
        t_load = time.monotonic() - t0

        session_files = rag._discover_session_files(args)
        print(
            f"[LEANN] Phase 2/3 — Construction de l'index "
            f"({len(session_files)} sessions, {len(texts)} chunks)...",
            flush=True,
        )
        t1 = time.monotonic()
        built_path = asyncio.run(rag.build_index(args, texts))
        t_build = time.monotonic() - t1

        rag._register_index(built_path)
        _build_full_manifest(rag, args)
        elapsed = time.monotonic() - t0
        print(
            f"[LEANN] Terminé ! {len(texts)} chunks indexés en {elapsed:.1f}s "
            f"(chargement {t_load:.1f}s, build {t_build:.1f}s)."
        )
        return

    # Incremental update
    print("[LEANN] Scanning sessions...", flush=True)
    t0 = time.monotonic()

    chunks, manifest = asyncio.run(rag._incremental_load(args))

    if not chunks:
        print("[LEANN] Index déjà à jour — rien à faire.")
        return

    t_load = time.monotonic() - t0
    print(f"[LEANN] {len(chunks)} chunks à indexer (scan {t_load:.1f}s)...", flush=True)

    try:
        t1 = time.monotonic()
        asyncio.run(rag._update_index(args, chunks, index_path))
        rag._register_index(index_path)
        _save_manifest(args.index_dir, manifest)
        t_build = time.monotonic() - t1
    except Exception as e:
        print(f"[LEANN] Erreur update_index : {e}")
        print("[LEANN] Fallback : reconstruction complète...")
        t1 = time.monotonic()
        texts = asyncio.run(rag.load_data(args))
        if texts:
            built_path = asyncio.run(rag.build_index(args, texts))
            rag._register_index(built_path)
            _build_full_manifest(rag, args)
        t_build = time.monotonic() - t1

    elapsed = time.monotonic() - t0
    print(f"[LEANN] Terminé ! {len(chunks)} chunks indexés en {elapsed:.1f}s.")


if __name__ == "__main__":
    main()
