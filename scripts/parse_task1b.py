#!/usr/bin/env python3
"""Collect Task 1B metrics from ChampSim outputs.

Reads   <out_dir>/{baseline,ip_stride,spp}/<trace>.txt
Writes  <out_dir>/metrics.csv, <out_dir>/metrics.md and, if matplotlib is
        installed, speedup/mpki/accuracy/coverage plots as PNGs.

Metrics (Region of Interest stats only):
  IPC        CPU 0 cumulative IPC
  Speedup    IPC / IPC of baseline (no prefetching)
  L1D MPKI   L1D LOAD MPKI
  Accuracy   L1D useful prefetches / prefetches issued to lower level (%)
  Coverage   (baseline L1D load misses - L1D load misses) / baseline misses (%)
"""

import csv
import math
import os
import re
import sys

CONFIGS = ["baseline", "ip_stride", "spp"]
LABELS = {"baseline": "Baseline", "ip_stride": "IP-stride", "spp": "SPP"}

RE_IPC = re.compile(r"CPU 0 cumulative IPC:\s*([\d.eE+-]+)")
RE_L1D_LOAD = re.compile(r"^L1D LOAD\s+ACCESS:\s*(\d+)\s+HIT:\s*(\d+)\s+MISS:\s*(\d+).*MPKI:\s*([\d.eE+-]+|nan|-?inf)", re.M)
RE_L1D_PF = re.compile(r"^L1D USEFUL LOAD PREFETCHES:\s*(\d+)\s+PREFETCH ISSUED TO LOWER LEVEL:\s*(\d+)", re.M)


def parse(path):
    with open(path, errors="replace") as f:
        text = f.read()
    marker = text.find("Region of Interest Statistics")
    if marker < 0:
        return None
    roi = text[marker:]

    ipc = RE_IPC.search(roi)
    load = RE_L1D_LOAD.search(roi)
    pf = RE_L1D_PF.search(roi)
    if not (ipc and load):
        return None

    useful, issued = (int(pf.group(1)), int(pf.group(2))) if pf else (0, 0)
    return {
        "ipc": float(ipc.group(1)),
        "l1d_load_miss": int(load.group(3)),
        "l1d_mpki": float(load.group(4)),
        "pf_useful": useful,
        "pf_issued": issued,
        "accuracy": 100.0 * useful / issued if issued else float("nan"),
    }


def geomean(xs):
    xs = [x for x in xs if x > 0 and not math.isnan(x)]
    return math.exp(sum(math.log(x) for x in xs) / len(xs)) if xs else float("nan")


def mean(xs):
    xs = [x for x in xs if not math.isnan(x)]
    return sum(xs) / len(xs) if xs else float("nan")


def fmt(x, digits=3):
    return "-" if x is None or (isinstance(x, float) and math.isnan(x)) else f"{x:.{digits}f}"


def main():
    out_dir = sys.argv[1] if len(sys.argv) > 1 else "results/task1b"

    traces = sorted({os.path.splitext(f)[0]
                     for cfg in CONFIGS if os.path.isdir(os.path.join(out_dir, cfg))
                     for f in os.listdir(os.path.join(out_dir, cfg)) if f.endswith(".txt")})

    data = {}
    for trace in traces:
        for cfg in CONFIGS:
            path = os.path.join(out_dir, cfg, trace + ".txt")
            data[(trace, cfg)] = parse(path) if os.path.exists(path) else None
            if data[(trace, cfg)] is None:
                print(f"[parse] missing or incomplete: {path}", file=sys.stderr)

    # keep only traces where the baseline finished (needed for speedup/coverage)
    traces = [t for t in traces if data[(t, "baseline")]]
    if not traces:
        print("[parse] no finished baseline runs found", file=sys.stderr)
        sys.exit(1)

    rows = []
    for trace in traces:
        base = data[(trace, "baseline")]
        for cfg in CONFIGS:
            d = data[(trace, cfg)]
            if d is None:
                continue
            speedup = d["ipc"] / base["ipc"]
            coverage = (100.0 * (base["l1d_load_miss"] - d["l1d_load_miss"]) / base["l1d_load_miss"]
                        if base["l1d_load_miss"] else float("nan"))
            rows.append({
                "trace": trace, "config": cfg,
                "ipc": d["ipc"], "speedup": speedup,
                "l1d_mpki": d["l1d_mpki"], "l1d_load_miss": d["l1d_load_miss"],
                "pf_issued": d["pf_issued"], "pf_useful": d["pf_useful"],
                "accuracy": d["accuracy"] if cfg != "baseline" else float("nan"),
                "coverage": coverage if cfg != "baseline" else float("nan"),
            })

    fields = ["trace", "config", "ipc", "speedup", "l1d_mpki", "l1d_load_miss",
              "pf_issued", "pf_useful", "accuracy", "coverage"]
    with open(os.path.join(out_dir, "metrics.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in rows:
            w.writerow({k: (fmt(v, 4) if isinstance(v, float) else v) for k, v in r.items()})

    def get(trace, cfg, key):
        for r in rows:
            if r["trace"] == trace and r["config"] == cfg:
                return r[key]
        return float("nan")

    # markdown table: one row per trace, plus a summary row
    pf_cfgs = [c for c in CONFIGS if c != "baseline"]
    header = (["Trace"] + [f"IPC {LABELS[c]}" for c in CONFIGS]
              + [f"Speedup {LABELS[c]}" for c in pf_cfgs]
              + [f"L1D MPKI {LABELS[c]}" for c in CONFIGS]
              + [f"Accuracy % {LABELS[c]}" for c in pf_cfgs]
              + [f"Coverage % {LABELS[c]}" for c in pf_cfgs])
    lines = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    for t in traces:
        cells = ([t] + [fmt(get(t, c, "ipc")) for c in CONFIGS]
                 + [fmt(get(t, c, "speedup")) for c in pf_cfgs]
                 + [fmt(get(t, c, "l1d_mpki")) for c in CONFIGS]
                 + [fmt(get(t, c, "accuracy"), 1) for c in pf_cfgs]
                 + [fmt(get(t, c, "coverage"), 1) for c in pf_cfgs])
        lines.append("| " + " | ".join(cells) + " |")
    summary = (["**Mean**"] + [fmt(mean([get(t, c, "ipc") for t in traces])) for c in CONFIGS]
               + [fmt(geomean([get(t, c, "speedup") for t in traces])) + " (geo)" for c in pf_cfgs]
               + [fmt(mean([get(t, c, "l1d_mpki") for t in traces])) for c in CONFIGS]
               + [fmt(mean([get(t, c, "accuracy") for t in traces]), 1) for c in pf_cfgs]
               + [fmt(mean([get(t, c, "coverage") for t in traces]), 1) for c in pf_cfgs])
    lines.append("| " + " | ".join(summary) + " |")
    table = "\n".join(lines)
    with open(os.path.join(out_dir, "metrics.md"), "w") as f:
        f.write(table + "\n")
    print(table)
    print(f"\n[parse] wrote {out_dir}/metrics.csv and {out_dir}/metrics.md")

    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        print("[parse] matplotlib not installed; skipping plots "
              "(pip install --user matplotlib, then rerun: python3 scripts/parse_task1b.py)")
        return

    colors = {"baseline": "#f08080", "ip_stride": "#6a7fb8", "spp": "#93acc8"}

    def bar_plot(key, cfgs, ylabel, title, fname, baseline_line=False):
        fig, ax = plt.subplots(figsize=(max(6, 1.6 * len(traces) + 2), 4.5))
        width = 0.8 / len(cfgs)
        for i, c in enumerate(cfgs):
            xs = [j + (i - (len(cfgs) - 1) / 2) * width for j in range(len(traces))]
            ax.bar(xs, [get(t, c, key) for t in traces], width,
                   label=LABELS[c], color=colors[c], edgecolor="grey")
        if baseline_line:
            ax.axhline(1.0, color="brown", linestyle="--", linewidth=1, label="Baseline")
        ax.set_xticks(range(len(traces)))
        ax.set_xticklabels(traces, rotation=20, ha="right")
        ax.set_ylabel(ylabel)
        ax.set_title(title)
        ax.legend(loc="upper left", bbox_to_anchor=(1.01, 1))
        fig.tight_layout()
        fig.savefig(os.path.join(out_dir, fname), dpi=150)
        plt.close(fig)

    bar_plot("speedup", pf_cfgs, "Speedup", "Speedup of L1D prefetchers over baseline (no prefetching)",
             "speedup.png", baseline_line=True)
    bar_plot("l1d_mpki", CONFIGS, "L1D load MPKI", "L1D load MPKI", "mpki.png")
    bar_plot("accuracy", pf_cfgs, "L1D prefetch accuracy (%)", "L1D prefetch accuracy", "accuracy.png")
    bar_plot("coverage", pf_cfgs, "L1D prefetch coverage (%)", "L1D prefetch coverage", "coverage.png")
    print(f"[parse] wrote speedup.png, mpki.png, accuracy.png, coverage.png in {out_dir}/")


if __name__ == "__main__":
    main()
