#!/bin/bash
# Task 2A experiments: LRU, SRRIP, I-RRIP and I-RRIP variants on every trace.
# Each simulator output is saved as results/task2a/<name>_<trace>.txt
#
# Run INSIDE the gcc-7 container:
#     ./scripts/run_task2a.sh       # phase A and B
#     ./scripts/run_task2a.sh A     # only lru / rrip / irrip
#     ./scripts/run_task2a.sh B     # only the I-RRIP variants
# Options (environment variables):
#     JOBS=3                         simulations at the same time
#     WARMUP=25000000 SIM=25000000   instruction counts (assignment: 25M + 25M)
#     TRACE_DIR=../traces            folder with Trace1.gz, Trace2.gz, Trace3.gz
#     OUT=results/task2a             folder for the result files
#     SKIP_BUILD=1                   use the existing binaries
#     FORCE=1                        re-run even if a finished result exists

cd "$(dirname "$0")/.." || exit 1          # repository root
PHASE=${1:-AB}
JOBS=${JOBS:-3}
WARMUP=${WARMUP:-25000000}
SIM=${SIM:-25000000}
TRACE_DIR=${TRACE_DIR:-../traces}
OUT=${OUT:-results/task2a}
mkdir -p "$OUT"

# Binary made by: ./build_champsim.sh no <policy> <policy>
bin_of() {
    echo "bin/hashed_perceptron-no-no-no-no-no-no-no-lru-lru-lru-$1-lru-lru-lru-lru-1core-$1"
}

# 1. Build, one at a time (builds share obj/ and the copied .cc files)
if [ -z "$SKIP_BUILD" ]; then
    for policy in lru rrip irrip; do
        echo "build $policy"
        if ! ./build_champsim.sh no $policy $policy > "$OUT/build_$policy.log" 2>&1; then
            echo "build of $policy FAILED, see $OUT/build_$policy.log"
            exit 1
        fi
    done
fi

# 2. Experiment list:  <name> <policy> <settings, comma separated, or ->
RUNS_A="lru lru -
rrip rrip -
irrip irrip -"
# I-RRIP variants (settings read by replacement/irrip.l2c_repl at start-up)
RUNS_B="irrip_none irrip IRRIP_INSTR_INSERT=2,IRRIP_DATA_HIT=0,IRRIP_DATA_FIRST=0
irrip_evict_only irrip IRRIP_INSTR_INSERT=2,IRRIP_DATA_HIT=0
irrip_insert_only irrip IRRIP_DATA_HIT=0,IRRIP_DATA_FIRST=0
irrip_promo_only irrip IRRIP_INSTR_INSERT=2,IRRIP_DATA_FIRST=0
irrip_aggressive irrip IRRIP_INSTR_INSERT=0"

# 3. Run one simulation; output goes to a .tmp file, renamed when it finishes
run_one() {   # <name> <policy> <settings> <trace>
    local name=$1 policy=$2 settings=$3 trace=$4
    local file="$OUT/${name}_${trace}.txt"
    if [ -z "$FORCE" ] && grep -q "ChampSim completed all CPUs" "$file" 2>/dev/null; then
        echo "skip  $name $trace (already done)"
        return 0
    fi
    local envs=""
    if [ "$settings" != "-" ]; then envs=${settings//,/ }; fi
    echo "$(date +%T) start $name $trace"
    if env $envs "$(bin_of "$policy")" -warmup_instructions "$WARMUP" \
            -simulation_instructions "$SIM" -traces "$TRACE_DIR/$trace.gz" > "$file.tmp" 2>&1; then
        mv "$file.tmp" "$file"
        echo "$(date +%T) done  $name $trace"
    else
        echo "$(date +%T) FAILED $name $trace (see $file.tmp)"
    fi
}
export -f run_one bin_of
export OUT WARMUP SIM TRACE_DIR FORCE

LIST=""
if [[ $PHASE == *A* ]]; then LIST+="$RUNS_A"$'\n'; fi
if [[ $PHASE == *B* ]]; then LIST+="$RUNS_B"$'\n'; fi

# 4. Every configuration x every trace, JOBS at a time
echo "$LIST" | while read -r name policy settings; do
    [ -z "$name" ] && continue
    for trace in Trace1 Trace2 Trace3; do
        echo "$name $policy $settings $trace"
    done
done | xargs -P "$JOBS" -L 1 bash -c 'run_one "$@"' _

echo "finished - results in $OUT/"
