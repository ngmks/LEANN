#!/usr/bin/env python3
"""Single indexation run for benchmarking. Deletes index, rebuilds, measures time.

Usage: uv run python benchmark/bench_run.py <model_name>
  e.g: uv run python benchmark/bench_run.py bge-m3
       uv run python benchmark/bench_run.py leann-bge-m3
"""
import asyncio
import shutil
import sys
import time
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "apps"))

INDEX_DIR = Path.home() / ".leann" / "indexes" / "claude-code-sessions"
WHITELIST = Path.home() / ".leann" / "whitelist.json"


def warmup(model: str, n: int = 3):
    print(f"[BENCH] Warm-up {model}...", end=" ", flush=True)
    for i in range(n):
        try:
            requests.post(
                "http://localhost:11434/api/embed",
                json={"model": model, "input": [f"warmup text number {i} with some content"]},
                timeout=30,
            )
        except Exception:
            pass
    print("ok")


def main():
    model = sys.argv[1] if len(sys.argv) > 1 else "bge-m3"

    # Delete index
    if INDEX_DIR.exists():
        shutil.rmtree(INDEX_DIR)
    INDEX_DIR.mkdir(parents=True, exist_ok=True)
    print(f"[BENCH] Index supprimé, model={model}")

    warmup(model)

    from claude_code_rag import ClaudeCodeRAG

    rag = ClaudeCodeRAG()
    args = rag.parser.parse_args([
        "--whitelist-file", str(WHITELIST),
        "--embedding-mode", "ollama",
        "--embedding-model", model,
        "--no-compact",
        "--no-recompute",
    ])

    t0 = time.monotonic()
    texts = asyncio.run(rag.load_data(args))
    t_load = time.monotonic() - t0
    print(f"[BENCH] {len(texts)} chunks chargés en {t_load:.1f}s")

    t1 = time.monotonic()
    built_path = asyncio.run(rag.build_index(args, texts))
    t_build = time.monotonic() - t1

    total = time.monotonic() - t0
    print(f"[BENCH] load={t_load:.1f}s | build={t_build:.1f}s | total={total:.1f}s | chunks={len(texts)}")


if __name__ == "__main__":
    main()
