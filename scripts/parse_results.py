#!/usr/bin/env python3
"""Collect ChampSim results into one table.

Reads every <config>_<trace>.txt in a results folder (made by
scripts/run_task2a.sh), extracts IPC and L2C MPKI values, computes the
speedup over the baseline config on the same trace and the geometric-mean
speedup over all traces, writes <folder>/summary.csv and prints a table.

Usage:  python3 scripts/parse_results.py [folder] [--baseline lru]
"""
import csv
import math
import os
import re
import sys

# value name -> regular expression that finds it in a ChampSim output file
PATTERNS = {
    "ipc":            r"^CPU 0 cumulative IPC: ([\d.]+)",
    "l2c_load_mpki":  r"^L2C LOAD\s+ACCESS:.*MPKI: ([\d.]+)",
    "l2c_instr_mpki": r"^L2C INSTRUCTION LOAD MPKI: ([\d.]+)",
    "l2c_data_mpki":  r"^L2C DATA LOAD MPKI: ([\d.]+)",
    "l2c_total_mpki": r"^L2C TOTAL\s+ACCESS:.*MPKI: ([\d.]+)",
    "instr_inserted": r"^L2C I-RRIP instruction lines inserted: (\d+)",
    "data_inserted":  r"^L2C I-RRIP data lines inserted: (\d+)",
    "instr_evicted":  r"^L2C I-RRIP instruction lines evicted: (\d+)",
    "data_evicted":   r"^L2C I-RRIP data lines evicted: (\d+)",
    # Dynamic I-RRIP (Task 2B) statistics
    "dyn_decisions":  r"^L2C DYN-IRRIP decisions: (\d+)",
    "dyn_switches":   r"^L2C DYN-IRRIP mode switches: (\d+)",
    "dyn_avg_ratio":  r"^L2C DYN-IRRIP average ratio: ([\d.e+-]+)",
    "dyn_irrip_pct":  r"^L2C DYN-IRRIP follower accesses in I-RRIP mode %: ([\d.e+-]+)",
}
COLUMNS = ["config", "trace", "ipc", "speedup"] + [k for k in PATTERNS if k != "ipc"]


def parse_file(path):
    """Return {value name: number} for one finished simulation output."""
    text = open(path).read()
    if "ChampSim completed all CPUs" not in text:
        return None                                  # unfinished or failed run
    values = {}
    for name, pattern in PATTERNS.items():
        m = re.search(pattern, text, re.MULTILINE)   # first match = ROI section
        if m:
            values[name] = float(m.group(1))
    return values


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    baseline = "lru"
    if "--baseline" in sys.argv:
        baseline = sys.argv[sys.argv.index("--baseline") + 1]
        args.remove(baseline)
    folder = args[0] if args else "results/task2a"

    # 1. read every <config>_<TraceN>.txt
    rows = {}
    for fname in sorted(os.listdir(folder)):
        m = re.match(r"(.+)_(Trace\d+)\.txt$", fname)
        if not m:
            continue
        values = parse_file(os.path.join(folder, fname))
        if values is None:
            print(f"skipping unfinished {fname}")
            continue
        rows[(m.group(1), m.group(2))] = values

    # 2. speedup = IPC / IPC of the baseline on the same trace
    for (config, trace), v in rows.items():
        base = rows.get((baseline, trace))
        v["speedup"] = v["ipc"] / base["ipc"] if base else float("nan")

    configs = sorted({c for c, _ in rows}, key=lambda c: (c != baseline, c))
    traces = sorted({t for _, t in rows})

    # 3. write summary.csv (one row per config and trace, plus a GEOMEAN row)
    out_path = os.path.join(folder, "summary.csv")
    with open(out_path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(COLUMNS)
        for config in configs:
            speedups = []
            for trace in traces:
                v = rows.get((config, trace))
                if v is None:
                    continue
                w.writerow([config, trace] + [round(v[k], 6) if k in v else "" for k in COLUMNS[2:]])
                speedups.append(v["speedup"])
            if speedups and not any(math.isnan(s) for s in speedups):
                geo = math.exp(sum(math.log(s) for s in speedups) / len(speedups))
                w.writerow([config, "GEOMEAN", "", round(geo, 6)])

    # 4. print a readable table
    print(f"{'config':<20}{'trace':<9}{'IPC':>9}{'speedup':>9}{'L2 load':>9}{'L2 instr':>9}{'L2 data':>9}")
    for config in configs:
        for trace in traces:
            v = rows.get((config, trace))
            if v:
                print(f"{config:<20}{trace:<9}{v['ipc']:>9.4f}{v['speedup']:>9.4f}"
                      f"{v.get('l2c_load_mpki', 0):>9.3f}{v.get('l2c_instr_mpki', 0):>9.3f}{v.get('l2c_data_mpki', 0):>9.3f}")
    print(f"\nwritten: {out_path}")


if __name__ == "__main__":
    main()
