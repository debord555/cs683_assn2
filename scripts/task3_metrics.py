#!/usr/bin/env python3
"""Task 3: metrics tables and plots for SPP + prefetch-aware Dynamic I-RRIP.

Compares four configurations on every trace:
  baseline   results/task1b/baseline/<trace>-*.txt   no L1D prefetching, LRU at L2
  spp        results/task1b/spp/<trace>-*.txt        SPP at L1D,          LRU at L2
  dyn_irrip  results/task2b/dyn_irrip_<trace>.txt    no L1D prefetching,  Dynamic I-RRIP at L2
  spp_dyn    results/task3/<trace>.txt               SPP at L1D,          prefetch-aware Dynamic I-RRIP at L2

Writes  results/task3/task3_metrics.csv       every metric, per trace and config
        results/task3/task3_table.md          all tables in markdown for the report
        results/task3/plots/speedup.png       speedup over the baseline
        results/task3/plots/ipc.png           IPC
        results/task3/plots/accuracy.png      L1D prefetch accuracy
        results/task3/plots/coverage.png      L1D prefetch coverage
        results/task3/plots/mpki.png          L1D, L2C, L2 instruction and L2 data load MPKI

Metrics (Region of Interest statistics, as defined in the assignment):
  IPC             CPU 0 cumulative IPC
  Speedup         IPC / IPC of the baseline (no prefetching, LRU) on the same trace
  Accuracy        ACCURACY of the "L1D USEFUL LOAD PREFETCHES" line (%)
  Coverage        (baseline L1D load misses - L1D load misses) / baseline L1D load misses (%)
  L1D MPKI        MPKI of the "L1D LOAD" line
  L2C MPKI        MPKI of the "L2C LOAD" line
  L2 instr MPKI   "L2C INSTRUCTION LOAD MPKI" line
  L2 data MPKI    "L2C DATA LOAD MPKI" line
The "Average" group is the geometric mean for speedup and the arithmetic mean
for every other metric.

Usage: python3 scripts/task3_metrics.py [--results results]
"""
import argparse
import csv
import math
import os
import re
import sys
import matplotlib
matplotlib.use("Agg")                       # draw to files, no window
import matplotlib.pyplot as plt

TRACES = ["Trace1", "Trace2", "Trace3"]
BASELINE = "baseline"
CONFIGS = ["baseline", "spp", "dyn_irrip", "spp_dyn"]
LABELS = {"baseline": "No prefetching (LRU)", "spp": "SPP (LRU)",
          "dyn_irrip": "Dyn-I-RRIP", "spp_dyn": "SPP + PF-aware Dyn-I-RRIP"}

# Same palette and styling as scripts/task1b_metrics.py
COLORS = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300"]
INK, MUTED, GRID = "#2C2C2A", "#5F5E5A", "#D3D1C7"
CONFIG_COLORS = {"baseline": COLORS[0], "spp": COLORS[1], "dyn_irrip": COLORS[2], "spp_dyn": COLORS[3]}

RE_IPC = re.compile(r"^CPU 0 cumulative IPC:\s*(\S+)", re.M)
RE_L1D_LOAD = re.compile(r"^L1D LOAD\s+ACCESS:\s*(\d+)\s+HIT:\s*(\d+)\s+MISS:\s*(\d+).*MPKI:\s*(\S+)", re.M)
RE_L1D_PF = re.compile(r"^L1D USEFUL LOAD PREFETCHES:\s*(\d+)\s+PREFETCH ISSUED TO LOWER LEVEL:\s*(\d+)"
                       r"\s+ACCURACY:\s*(\S+)", re.M)
RE_L2_LOAD = re.compile(r"^L2C LOAD\s+ACCESS:\s*(\d+)\s+HIT:\s*(\d+)\s+MISS:\s*(\d+).*MPKI:\s*(\S+)", re.M)
RE_L2_INSTR = re.compile(r"^L2C INSTRUCTION LOAD MPKI:\s*(\S+)", re.M)
RE_L2_DATA = re.compile(r"^L2C DATA LOAD MPKI:\s*(\S+)", re.M)
RE_L2_PF = re.compile(r"^L2C PREFETCH\s+ACCESS:\s*(\d+)\s+HIT:\s*(\d+)\s+MISS:\s*(\d+)", re.M)
# prefetched L2 lines later hit by a demand load / prefetched lines filled into L2
RE_L2_PF_USEFUL = re.compile(r"^L2C USEFUL LOAD PREFETCHES:\s*(\d+)\s+PREFETCH ISSUED TO LOWER LEVEL:\s*(\d+)", re.M)
RE_DYN = {"dyn_irrip_pct": re.compile(r"^L2C DYN-IRRIP follower accesses in I-RRIP mode %:\s*(\S+)", re.M),
          "dyn_switches": re.compile(r"^L2C DYN-IRRIP mode switches:\s*(\S+)", re.M),
          "dyn_ratio": re.compile(r"^L2C DYN-IRRIP average ratio:\s*(\S+)", re.M),
          "pf_inserts": re.compile(r"^L2C DYN-IRRIP prefetch lines inserted at max RRPV:\s*(\S+)", re.M),
          "pf_l2_hits": re.compile(r"^L2C DYN-IRRIP prefetch hits \(not promoted\):\s*(\S+)", re.M)}

# (title, key, digits) for every metric of the deliverables
METRICS = [("IPC", "ipc", 4),
           ("Speedup over no prefetching (LRU)", "speedup", 4),
           ("L1D prefetch accuracy (%)", "accuracy", 2),
           ("L1D prefetch coverage (%)", "coverage", 2),
           ("L1D load MPKI", "l1d_mpki", 3),
           ("L2C load MPKI", "l2_mpki", 3),
           ("L2 instruction load MPKI", "l2_instr_mpki", 3),
           ("L2 data load MPKI", "l2_data_mpki", 3)]
EXTRA = ["l1d_load_miss", "pf_issued", "pf_useful", "l2_pf_access", "l2_pf_hit", "l2_pf_miss",
         "l2_pf_useful", "l2_pf_useful_pct",
         "dyn_ratio", "dyn_irrip_pct", "dyn_switches", "pf_inserts", "pf_l2_hits"]
NAN = float("nan")


def num(s):
    try:
        return float(s)
    except ValueError:                      # "-nan" when nothing was issued
        return NAN


def parse(path):
    """Region of Interest stats of one run, or None if the run did not finish."""
    with open(path, errors="replace") as f:
        text = f.read()
    start = text.find("Region of Interest Statistics")
    if start < 0:
        return None
    roi = text[start:]
    found = [r.search(roi) for r in (RE_IPC, RE_L1D_LOAD, RE_L1D_PF, RE_L2_LOAD, RE_L2_INSTR, RE_L2_DATA)]
    if not all(found):
        return None
    ipc, l1, pf, l2, l2i, l2d = found
    l2pf = RE_L2_PF.search(roi)
    l2u = RE_L2_PF_USEFUL.search(roi)
    r = {"ipc": num(ipc.group(1)),
         "l1d_load_miss": int(l1.group(3)), "l1d_mpki": num(l1.group(4)),
         "pf_useful": int(pf.group(1)), "pf_issued": int(pf.group(2)), "accuracy": num(pf.group(3)),
         "l2_mpki": num(l2.group(4)), "l2_instr_mpki": num(l2i.group(1)), "l2_data_mpki": num(l2d.group(1)),
         "l2_pf_access": int(l2pf.group(1)) if l2pf else 0,
         "l2_pf_hit": int(l2pf.group(2)) if l2pf else 0,
         "l2_pf_miss": int(l2pf.group(3)) if l2pf else 0,
         "l2_pf_useful": int(l2u.group(1)) if l2u else 0}
    r["l2_pf_useful_pct"] = 100.0 * r["l2_pf_useful"] / r["l2_pf_miss"] if r["l2_pf_miss"] else NAN
    for key, rx in RE_DYN.items():
        m = rx.search(roi)
        r[key] = num(m.group(1)) if m else NAN
    return r


def find_run(results, config, trace):
    """Path of the output file of one configuration on one trace, or None."""
    if config in ("baseline", "spp"):
        folder = os.path.join(results, "task1b", config)
        names = [n for n in sorted(os.listdir(folder)) if n == trace + ".txt" or n.startswith(trace + "-")] \
            if os.path.isdir(folder) else []
        return os.path.join(folder, names[0]) if names else None
    path = os.path.join(results, "task2b", f"dyn_irrip_{trace}.txt") if config == "dyn_irrip" \
        else os.path.join(results, "task3", f"{trace}.txt")
    return path if os.path.isfile(path) else None


def geomean(xs):
    xs = [x for x in xs if x > 0 and not math.isnan(x)]
    return math.exp(sum(map(math.log, xs)) / len(xs)) if xs else NAN


def mean(xs):
    xs = [x for x in xs if not math.isnan(x)]
    return sum(xs) / len(xs) if xs else NAN


def fmt(x, digits):
    return "-" if x is None or math.isnan(x) else f"{x:.{digits}f}"


def csv_value(v):
    if isinstance(v, float):
        return "" if math.isnan(v) else f"{v:.6f}"
    return v


def style(ax, title, ylabel):
    """Quiet axes: light grid, no box, title says what is better."""
    ax.set_title(title, fontsize=10, color=INK, loc="left", fontweight="bold")
    ax.set_ylabel(ylabel, fontsize=8.5, color=MUTED)
    ax.tick_params(axis="y", labelsize=8, colors=MUTED, length=0)
    ax.tick_params(axis="x", labelsize=8.5, colors=INK, length=0)
    ax.grid(axis="y", color=GRID, lw=0.6, zorder=0)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(GRID)


def grouped_bars(ax, data, groups, configs, key, base=0.0, digits=2, fontsize=6.5):
    """One group of bars per trace (+ Average), one bar per config, value on top."""
    width = 0.8 / len(configs)
    for i, config in enumerate(configs):
        xs, values = [], []
        for g, group in enumerate(groups):
            v = data.get((config, group), {}).get(key, NAN)
            if not math.isnan(v):
                xs.append(g - 0.4 + width * (i + 0.5))
                values.append(v)
        ax.bar(xs, [v - base for v in values], width * 0.9, bottom=base,
               color=CONFIG_COLORS[config], label=LABELS[config], zorder=3)
        for x, v in zip(xs, values):
            ax.text(x, v, fmt(v, digits), ha="center", va="bottom" if v >= base else "top",
                    fontsize=fontsize, color=INK, rotation=90 if len(configs) > 3 else 0)
    ax.set_xticks(range(len(groups)))
    ax.set_xticklabels(groups)
    low, high = ax.get_ylim()
    ax.set_ylim(low, high + (high - low) * 0.3)           # room for value labels and legend


def save(fig, ax, path, ncol):
    ax.legend(fontsize=7.5, frameon=False, ncol=ncol, loc="upper left")
    fig.tight_layout()
    fig.savefig(path, dpi=200)
    plt.close(fig)


def md_table(title, header, rows):
    return [f"## {title}", "", "| " + " | ".join(header) + " |",
            "|---|" + "---:|" * (len(header) - 1)] + ["| " + " | ".join(r) + " |" for r in rows] + [""]


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--results", default="results", help="results folder (default: results)")
    args = ap.parse_args()

    # ---- parse ----
    raw = {}
    for config in CONFIGS:
        for trace in TRACES:
            path = find_run(args.results, config, trace)
            stats = parse(path) if path else None
            if stats is None:
                print(f"[task3] {config}: no finished run for {trace}", file=sys.stderr)
            else:
                raw[(config, trace)] = stats
    traces = [t for t in TRACES if (BASELINE, t) in raw]
    if not traces:
        sys.exit("[task3] no finished baseline runs")

    # ---- metrics ----
    data = {}
    for (config, trace), r in raw.items():
        if trace not in traces:
            continue
        base = raw[(BASELINE, trace)]
        prefetching = config in ("spp", "spp_dyn")
        data[(config, trace)] = dict(
            r, speedup=r["ipc"] / base["ipc"],
            accuracy=r["accuracy"] if prefetching else NAN,
            coverage=100.0 * (base["l1d_load_miss"] - r["l1d_load_miss"]) / base["l1d_load_miss"]
            if prefetching else NAN)
    for config in CONFIGS:
        rows = [data[(config, t)] for t in traces if (config, t) in data]
        data[(config, "Average")] = {
            "speedup": geomean([r["speedup"] for r in rows]),
            **{k: mean([r[k] for r in rows]) for _, k, _ in METRICS if k != "speedup"}}
    groups = traces + ["Average"]

    # ---- CSV ----
    out_dir = os.path.join(args.results, "task3")
    fields = [k for _, k, _ in METRICS] + EXTRA
    csv_path = os.path.join(out_dir, "task3_metrics.csv")
    with open(csv_path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["trace", "config"] + fields)
        for trace in groups:
            for config in CONFIGS:
                r = data.get((config, trace))
                if r:
                    w.writerow([trace, config] + [csv_value(r.get(k, "")) for k in fields])

    # ---- markdown tables ----
    lines = ["# Task 3 results", "",
             "Baseline: no L1D prefetching, LRU at L2 (results/task1b/baseline).", ""]
    for title, key, digits in METRICS:
        cfgs = [c for c in CONFIGS if c in ("spp", "spp_dyn")] if key in ("accuracy", "coverage") else \
            CONFIGS[1:] if key == "speedup" else CONFIGS
        if key == "speedup":
            title += " (Average = geometric mean)"
        lines += md_table(title, ["Trace"] + [LABELS[c] for c in cfgs], [
            ["**Average**" if g == "Average" else g] +
            [fmt(data.get((c, g), {}).get(key, NAN), digits) for c in cfgs] for g in groups])
    rows = []
    for trace in traces:
        for config in ("spp", "spp_dyn"):
            r = data.get((config, trace))
            if r:
                rows.append([trace, LABELS[config], str(r["pf_issued"]), str(r["pf_useful"]),
                             str(r["l2_pf_hit"]), str(r["l2_pf_miss"]), str(r["l2_pf_useful"]),
                             fmt(r["l2_pf_useful_pct"], 2)])
    lines += md_table("Prefetch traffic at L1D and L2",
                      ["Trace", "Config", "L1D PF issued", "L1D PF useful", "PF hits in L2",
                       "PF fills into L2", "L2 PF lines hit by a demand load", "% of L2 PF fills used"], rows)
    rows = []
    for trace in traces:
        for config in ("dyn_irrip", "spp_dyn"):
            r = data.get((config, trace))
            if r:
                rows.append([trace, LABELS[config], fmt(r["dyn_ratio"], 3), fmt(r["dyn_irrip_pct"], 1),
                             fmt(r["dyn_switches"], 0)])
    lines += md_table("Set-dueling decision",
                      ["Trace", "Config", "Average ratio", "% follower accesses in I-RRIP mode", "Switches"],
                      rows)

    md_path = os.path.join(out_dir, "task3_table.md")
    with open(md_path, "w") as f:
        f.write("\n".join(lines))
    print("\n".join(lines))

    # ---- plots ----
    out = os.path.join(out_dir, "plots")
    os.makedirs(out, exist_ok=True)
    others = CONFIGS[1:]
    pf = ["spp", "spp_dyn"]

    fig, ax = plt.subplots(figsize=(7.5, 3.8))
    grouped_bars(ax, data, groups, others, "speedup", base=1.0, digits=4)
    ax.axhline(1.0, color=CONFIG_COLORS[BASELINE], lw=1.2, ls="--", zorder=4,
               label=f"{LABELS[BASELINE]} (baseline)")
    style(ax, "Speedup over no prefetching, LRU (higher is better)", "speedup")
    save(fig, ax, os.path.join(out, "speedup.png"), ncol=2)

    for key, digits, title, ylabel, cfgs in [
            ("ipc", 4, "IPC (higher is better)", "instructions per cycle", CONFIGS),
            ("accuracy", 1, "L1D prefetch accuracy (higher is better)", "useful / issued prefetches (%)", pf),
            ("coverage", 2, "L1D prefetch coverage (higher is better)", "baseline load misses removed (%)", pf)]:
        fig, ax = plt.subplots(figsize=(7.5, 3.8))
        grouped_bars(ax, data, groups, cfgs, key, digits=digits)
        style(ax, title, ylabel)
        save(fig, ax, os.path.join(out, key + ".png"), ncol=2)

    fig, axes = plt.subplots(2, 2, figsize=(11, 7))
    for ax, (key, title) in zip(axes.flat, [("l1d_mpki", "L1D load MPKI"), ("l2_mpki", "L2C load MPKI"),
                                            ("l2_instr_mpki", "L2 instruction load MPKI"),
                                            ("l2_data_mpki", "L2 data load MPKI")]):
        grouped_bars(ax, data, groups, CONFIGS, key, digits=2, fontsize=6)
        style(ax, title + " (lower is better)", "misses / 1000 instructions")
    axes.flat[0].legend(fontsize=7.5, frameon=False, ncol=2, loc="upper left")
    fig.tight_layout()
    fig.savefig(os.path.join(out, "mpki.png"), dpi=200)
    plt.close(fig)

    print(f"[task3] wrote {csv_path}, {md_path}")
    print(f"[task3] wrote speedup.png, ipc.png, accuracy.png, coverage.png, mpki.png in {out}/")


if __name__ == "__main__":
    main()
