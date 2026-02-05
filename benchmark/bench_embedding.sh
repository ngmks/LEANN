#!/usr/bin/env bash
# Benchmark: Flash Attention (ON/OFF) × num_ctx (4096/8192) pour bge-m3
set -euo pipefail

LEANN_ROOT=/home/mks/projects/leann-fork
OVERRIDE=/etc/systemd/system/ollama.service.d/override.conf
RESULTS=$LEANN_ROOT/benchmark/results.txt
TMPOUT=$LEANN_ROOT/benchmark/last_run.log

set_flash() {
    local on="$1"
    if [ "$on" = "on" ]; then
        printf '[Service]\n# flash attention ON\n' | sudo tee "$OVERRIDE" > /dev/null
    else
        printf '[Service]\nEnvironment="OLLAMA_FLASH_ATTENTION=false"\n' | sudo tee "$OVERRIDE" > /dev/null
    fi
    sudo systemctl daemon-reload
    sudo systemctl restart ollama
    for i in $(seq 1 30); do
        curl -s http://localhost:11434/api/tags > /dev/null 2>&1 && break
        sleep 1
    done
    echo "Ollama restarted (flash_attention=$on)"
}

run() {
    local label="$1" model="$2"
    echo ""
    echo "━━━ $label (model=$model) ━━━"
    cd "$LEANN_ROOT"
    uv run python benchmark/bench_run.py "$model" > "$TMPOUT" 2>&1 || true
    cat "$TMPOUT"
    # Extract the summary line
    local summary
    summary=$(grep 'total=' "$TMPOUT" | tail -1)
    echo "$label | $summary" >> "$RESULTS"
}

echo "BENCHMARK: Flash Attention x num_ctx"
echo "======================================"
: > "$RESULTS"

echo ""
echo "== Flash Attention OFF =="
set_flash off
run "Flash_OFF+ctx4096" "bge-m3"
run "Flash_OFF+ctx8192" "leann-bge-m3"

echo ""
echo "== Flash Attention ON =="
set_flash on
run "Flash_ON+ctx4096"  "bge-m3"
run "Flash_ON+ctx8192"  "leann-bge-m3"

echo ""
echo "Restauration flash_attention=off..."
set_flash off

echo ""
echo "====== RESULTATS ======"
cat "$RESULTS"
