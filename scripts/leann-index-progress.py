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
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# Make apps/ importable
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "apps"))


def _build_full_manifest(rag, args) -> dict:
    """Build and save a full manifest after a complete index build."""
    from claude_code_rag import _count_lines, _file_mtime, _save_manifest
    from claude_code_data.claude_code_reader import ClaudeCodeReader

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
    print("[LEANN] Démarrage de l'indexation incrémentale...")

    from claude_code_rag import ClaudeCodeRAG, _save_manifest

    rag = ClaudeCodeRAG()
    args = rag.parser.parse_args([
        "--whitelist-file", str(Path.home() / ".leann" / "whitelist.json"),
        "--embedding-mode", "ollama",
        "--embedding-model", "bge-m3",
        "--no-compact",
        "--no-recompute",
    ])

    index_path = str(Path(args.index_dir) / f"{rag.default_index_name}.leann")
    meta_file = Path(index_path + ".meta.json")

    if not meta_file.exists():
        print("[LEANN] Aucun index existant. Lancement d'un build complet...")
        t0 = time.monotonic()

        texts = asyncio.run(rag.load_data(args))
        if not texts:
            print("[LEANN] Aucune donnée trouvée !")
            return

        print(f"[LEANN] {len(texts)} chunks à indexer...")
        built_path = asyncio.run(rag.build_index(args, texts))
        rag._register_index(built_path)
        _build_full_manifest(rag, args)
        elapsed = time.monotonic() - t0
        print(f"[LEANN] Terminé ! {len(texts)} chunks indexés en {elapsed:.1f}s.")
        return

    # Incremental update
    print("[LEANN] Scanning sessions...")
    t0 = time.monotonic()

    chunks, manifest = asyncio.run(rag._incremental_load(args))

    if not chunks:
        print("[LEANN] Index déjà à jour — rien à faire.")
        return

    print(f"[LEANN] {len(chunks)} chunks à indexer...")

    try:
        asyncio.run(rag._update_index(args, chunks, index_path))
        rag._register_index(index_path)
        _save_manifest(args.index_dir, manifest)
    except Exception as e:
        print(f"[LEANN] Erreur update_index : {e}")
        print("[LEANN] Fallback : reconstruction complète...")
        texts = asyncio.run(rag.load_data(args))
        if texts:
            built_path = asyncio.run(rag.build_index(args, texts))
            rag._register_index(built_path)
            _build_full_manifest(rag, args)

    elapsed = time.monotonic() - t0
    print(f"[LEANN] Terminé ! {len(chunks)} chunks indexés en {elapsed:.1f}s.")


if __name__ == "__main__":
    main()
