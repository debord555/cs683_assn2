#!/bin/bash
# Task 1B: build baseline / IP-stride / SPP, run every trace, then collect metrics.
#
# Usage: scripts/run_task1b.sh [TRACE_DIR] [JOBS]
#   TRACE_DIR  directory with *.champsimtrace.xz files (default: ../traces)
#   JOBS       simulations to run in parallel          (default: nproc)
#
# Building needs g++-7 (run inside the container: ./start_container.sh).
# The binaries are static, so simulations can also run on the host once built.
# Set REBUILD=1 to force rebuilding the binaries, RERUN=1 to redo finished runs.

set -euo pipefail

cd "$(dirname "$0")/.."

TRACE_DIR=${1:-../traces}
JOBS=${2:-$(nproc)}
WARMUP=25000000
SIM=25000000
OUT_DIR=results/task1b

# config name -> L1D prefetcher (prefetcher/<name>.l1d_pref)
CONFIGS=(baseline ip_stride spp)
declare -A PREFETCHER=([baseline]=no [ip_stride]=ip_stride [spp]=spp)

binary_for() {
    echo "bin/hashed_perceptron-no-${PREFETCHER[$1]}-no-no-no-no-no-lru-lru-lru-lru-lru-lru-lru-lru-1core-task1b_$1"
}

# ---- build ----
for cfg in "${CONFIGS[@]}"; do
    bin=$(binary_for "$cfg")
    if [ -x "$bin" ] && [ "${REBUILD:-0}" != 1 ]; then
        echo "[build] $cfg: using existing $bin"
        continue
    fi
    if ! command -v g++-7 >/dev/null; then
        echo "[build] ERROR: g++-7 not found; build inside the container (./start_container.sh)" >&2
        exit 1
    fi
    echo "[build] $cfg (L1D prefetcher: ${PREFETCHER[$cfg]})"
    ./build_champsim.sh "${PREFETCHER[$cfg]}" lru "task1b_$cfg" > "build_task1b_$cfg.txt" 2>&1 \
        || { echo "[build] FAILED, see build_task1b_$cfg.txt" >&2; exit 1; }
    rm -f "build_task1b_$cfg.txt"
done

# ---- run ----
shopt -s nullglob
TRACES=("$TRACE_DIR"/*.champsimtrace.xz)
if [ ${#TRACES[@]} -eq 0 ]; then
    echo "[run] ERROR: no *.champsimtrace.xz files in $TRACE_DIR" >&2
    exit 1
fi

JOB_LIST=$(mktemp)
for cfg in "${CONFIGS[@]}"; do
    mkdir -p "$OUT_DIR/$cfg"
    for trace in "${TRACES[@]}"; do
        name=$(basename "$trace" .champsimtrace.xz)
        out="$OUT_DIR/$cfg/$name.txt"
        if [ "${RERUN:-0}" != 1 ] && [ -f "$out" ] && grep -q "Region of Interest Statistics" "$out"; then
            continue
        fi
        echo "$(binary_for "$cfg") $trace $out" >> "$JOB_LIST"
    done
done

N=$(wc -l < "$JOB_LIST")
echo "[run] $N simulations to run, $JOBS at a time (results in $OUT_DIR/)"
if [ "$N" -gt 0 ]; then
    xargs -P "$JOBS" -L 1 sh -c '
        echo "[run] start  $(basename "$2") -> $3"
        "$1" -warmup_instructions '"$WARMUP"' -simulation_instructions '"$SIM"' -traces "$2" > "$3" 2>&1 \
            && echo "[run] done   $3" || echo "[run] FAILED $3"
    ' _ < "$JOB_LIST"
fi
rm -f "$JOB_LIST"

# ---- collect ----
python3 scripts/parse_task1b.py "$OUT_DIR"
