#!/usr/bin/env python3
"""Benchmark: Flash Attention (ON/OFF) × num_ctx (4096/8192) for bge-m3 embeddings.

Uses real Claude Code session JSONL files from benchmark/sessions/.
Measures embedding speed only (no index building).
"""

import json
import os
import subprocess
import sys
import time
from pathlib import Path

import requests

# ── Config ──────────────────────────────────────────────────────────────────
OLLAMA_URL = "http://localhost:11434"
EMBED_URL = f"{OLLAMA_URL}/api/embed"
BASE_MODEL = "bge-m3"
BATCH_SIZE = 128
SESSIONS_DIR = Path(__file__).parent / "sessions"
RESULTS_FILE = Path(__file__).parent / "results.json"

# We'll create temporary models for each num_ctx variant
MODELS = {
    4096: "bench-bge-m3-4k",
    8192: "bench-bge-m3-8k",
}


# ── Text extraction (simplified reader) ────────────────────────────────────
def extract_texts_from_sessions(sessions_dir: Path, max_texts: int = 0) -> list[str]:
    """Extract user+assistant text from JSONL session files."""
    texts = []
    for jsonl_file in sorted(sessions_dir.glob("*.jsonl")):
        try:
            with open(jsonl_file, "r", errors="replace") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entry = json.loads(line)
                    except json.JSONDecodeError:
                        continue

                    # Claude Code JSONL: top-level "type" field is "user"/"assistant"
                    entry_type = entry.get("type", "")
                    if entry_type not in ("user", "assistant"):
                        continue

                    # Content is in entry.message.content
                    message = entry.get("message", {})
                    if not isinstance(message, dict):
                        continue
                    content = message.get("content", "")

                    # Extract text, chunk into ~500 char pieces
                    raw_texts = []
                    if isinstance(content, str) and len(content) > 20:
                        raw_texts.append(content)
                    elif isinstance(content, list):
                        for block in content:
                            if isinstance(block, dict) and block.get("type") == "text":
                                text = block.get("text", "")
                                if len(text) > 20:
                                    raw_texts.append(text)

                    for raw in raw_texts:
                        for i in range(0, len(raw), 500):
                            chunk = raw[i : i + 500]
                            if len(chunk) > 20:
                                texts.append(chunk)

                    if max_texts and len(texts) >= max_texts:
                        return texts[:max_texts]
        except Exception as e:
            print(f"  skip {jsonl_file.name}: {e}", file=sys.stderr)
    return texts


# ── Ollama helpers ──────────────────────────────────────────────────────────
def create_models():
    """Create Ollama model variants for each num_ctx value."""
    for ctx, name in MODELS.items():
        modelfile = f"FROM {BASE_MODEL}\nPARAMETER num_ctx {ctx}\n"
        resp = requests.post(
            f"{OLLAMA_URL}/api/create",
            json={"name": name, "modelfile": modelfile},
            stream=True,
        )
        for line in resp.iter_lines():
            pass
        print(f"  Created model {name} (num_ctx={ctx})")


def warmup_model(model: str, n: int = 3):
    """Warm up the model with a few embedding calls."""
    for i in range(n):
        requests.post(EMBED_URL, json={"model": model, "input": [f"warmup text {i}"]})
    print(f"  Warmed up {model} ({n} calls)")


def embed_batch(model: str, texts: list[str]) -> tuple[float, bool, str]:
    """Embed a batch, return (elapsed_seconds, success, error_msg)."""
    start = time.perf_counter()
    try:
        resp = requests.post(
            EMBED_URL,
            json={"model": model, "input": texts},
            timeout=120,
        )
        elapsed = time.perf_counter() - start
        if resp.status_code == 200:
            return elapsed, True, ""
        else:
            err = resp.text[:200]
            return elapsed, False, err
    except Exception as e:
        elapsed = time.perf_counter() - start
        return elapsed, False, str(e)


def set_flash_attention(enabled: bool):
    """Toggle flash attention via systemd override and restart Ollama."""
    override_dir = "/etc/systemd/system/ollama.service.d"
    override_file = f"{override_dir}/override.conf"

    if enabled:
        # Remove the override (flash attention is ON by default)
        content = "[Service]\n# Flash attention enabled (default)\n"
    else:
        content = '[Service]\nEnvironment="OLLAMA_FLASH_ATTENTION=false"\n'

    # Write override
    subprocess.run(
        ["sudo", "tee", override_file],
        input=content.encode(),
        stdout=subprocess.DEVNULL,
        check=True,
    )
    # Reload and restart
    subprocess.run(["sudo", "systemctl", "daemon-reload"], check=True)
    subprocess.run(["sudo", "systemctl", "restart", "ollama"], check=True)
    print(f"  Ollama restarted (flash_attention={'ON' if enabled else 'OFF'})")

    # Wait for Ollama to be ready
    for attempt in range(30):
        try:
            r = requests.get(f"{OLLAMA_URL}/api/tags", timeout=2)
            if r.status_code == 200:
                print(f"  Ollama ready (attempt {attempt + 1})")
                # Recreate test models (lost on restart)
                create_models()
                return
        except Exception:
            pass
        time.sleep(1)
    raise RuntimeError("Ollama did not start in 30s")


# ── Benchmark ───────────────────────────────────────────────────────────────
def benchmark_combo(
    model: str, texts: list[str], batch_size: int, label: str
) -> dict:
    """Run a full benchmark for one combination."""
    n_batches = len(texts) // batch_size
    if n_batches == 0:
        n_batches = 1

    total_texts = n_batches * batch_size
    batches = [texts[i * batch_size : (i + 1) * batch_size] for i in range(n_batches)]

    print(f"\n{'─' * 60}")
    print(f"  {label}")
    print(f"  Model: {model} | {n_batches} batches × {batch_size} texts = {total_texts} texts")
    print(f"{'─' * 60}")

    warmup_model(model, n=3)

    times = []
    errors = 0
    error_msgs = []

    for i, batch in enumerate(batches):
        elapsed, success, err = embed_batch(model, batch)
        if success:
            times.append(elapsed)
            status = f"{elapsed:.2f}s"
        else:
            errors += 1
            error_msgs.append(err)
            status = f"FAIL ({err[:60]})"
        # Progress every 10 batches
        if (i + 1) % 10 == 0 or i == 0 or i == n_batches - 1:
            print(f"  batch {i + 1:3d}/{n_batches}: {status}")

    result = {
        "label": label,
        "model": model,
        "batch_size": batch_size,
        "total_texts": total_texts,
        "n_batches": n_batches,
        "successful_batches": len(times),
        "failed_batches": errors,
        "total_time_s": sum(times),
        "avg_batch_s": sum(times) / len(times) if times else 0,
        "texts_per_sec": total_texts / sum(times) if times else 0,
        "min_batch_s": min(times) if times else 0,
        "max_batch_s": max(times) if times else 0,
    }

    if errors:
        result["error_rate_pct"] = round(errors / n_batches * 100, 1)
        result["sample_errors"] = error_msgs[:3]

    print(f"\n  Résultat: {result['total_time_s']:.1f}s total | "
          f"{result['texts_per_sec']:.0f} texts/s | "
          f"{result['avg_batch_s']:.2f}s/batch | "
          f"erreurs: {errors}/{n_batches}")

    return result


def main():
    print("=" * 60)
    print("  BENCHMARK: Flash Attention × num_ctx pour bge-m3")
    print("=" * 60)

    # ── Extract texts ───────────────────────────────────────────
    print(f"\nExtraction des textes depuis {SESSIONS_DIR}...")
    texts = extract_texts_from_sessions(SESSIONS_DIR)
    print(f"  {len(texts)} chunks extraits")

    # Truncate to a round number of batches
    n_usable = (len(texts) // BATCH_SIZE) * BATCH_SIZE
    texts = texts[:n_usable]
    print(f"  {n_usable} textes utilisés ({n_usable // BATCH_SIZE} batches de {BATCH_SIZE})")

    # ── Create test models ──────────────────────────────────────
    print("\nCréation des modèles de test...")
    create_models()

    results = []

    # ── Phase 1: Flash Attention OFF (current state) ────────────
    print("\n" + "═" * 60)
    print("  PHASE 1 : Flash Attention OFF")
    print("═" * 60)

    # Ensure flash attention is OFF (should be current state)
    set_flash_attention(enabled=False)

    for ctx, model in MODELS.items():
        label = f"Flash_OFF + num_ctx={ctx}"
        r = benchmark_combo(model, texts, BATCH_SIZE, label)
        r["flash_attention"] = False
        r["num_ctx"] = ctx
        results.append(r)

    # ── Phase 2: Flash Attention ON ─────────────────────────────
    print("\n" + "═" * 60)
    print("  PHASE 2 : Flash Attention ON")
    print("═" * 60)

    set_flash_attention(enabled=True)

    for ctx, model in MODELS.items():
        label = f"Flash_ON  + num_ctx={ctx}"
        r = benchmark_combo(model, texts, BATCH_SIZE, label)
        r["flash_attention"] = True
        r["num_ctx"] = ctx
        results.append(r)

    # ── Restore: Flash Attention OFF ────────────────────────────
    print("\nRestauration: Flash Attention OFF...")
    set_flash_attention(enabled=False)

    # ── Cleanup test models ─────────────────────────────────────
    print("\nNettoyage des modèles de test...")
    for name in MODELS.values():
        try:
            requests.delete(f"{OLLAMA_URL}/api/delete", json={"name": name})
            print(f"  Deleted {name}")
        except Exception:
            pass

    # ── Results summary ─────────────────────────────────────────
    print("\n" + "═" * 60)
    print("  RÉSULTATS COMPARATIFS")
    print("═" * 60)
    print(f"\n  {'Combinaison':<30} {'Total':>8} {'texts/s':>10} {'Erreurs':>10}")
    print(f"  {'─' * 30} {'─' * 8} {'─' * 10} {'─' * 10}")
    for r in results:
        errs = f"{r['failed_batches']}/{r['n_batches']}"
        print(f"  {r['label']:<30} {r['total_time_s']:>7.1f}s {r['texts_per_sec']:>9.0f} {errs:>10}")

    # ── Save results ────────────────────────────────────────────
    with open(RESULTS_FILE, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nRésultats sauvegardés dans {RESULTS_FILE}")


if __name__ == "__main__":
    main()
