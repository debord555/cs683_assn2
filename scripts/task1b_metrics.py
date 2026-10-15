#!/usr/bin/env python3
"""Task 1B: metrics table and plots from the ChampSim outputs.

Reads   <folder>/<config>/<trace>.txt   for every config folder found
        (baseline = no L1D prefetching, e.g. ip_stride, spp, spp_small)
Writes  <folder>/task1b_metrics.csv     every metric, per trace and config
        <folder>/task1b_table.md        the same as markdown tables for the report
        <folder>/plots/speedup.png      speedup over the baseline
        <folder>/plots/mpki.png         L1D load MPKI
        <folder>/plots/accuracy.png     L1D prefetch accuracy
        <folder>/plots/coverage.png     L1D prefetch coverage
        <folder>/plots/ipc.png          IPC

Metrics (Region of Interest statistics, as defined in the assignment):
  IPC        CPU 0 cumulative IPC
  Speedup    IPC with prefetcher / IPC of baseline (no prefetching)
  L1D MPKI   MPKI of the "L1D LOAD" line
  Accuracy   ACCURACY of the "L1D USEFUL LOAD PREFETCHES" line
             (useful load prefetches / prefetches issued to lower level, %)
  Coverage   (baseline L1D load misses - L1D load misses) / baseline L1D load misses (%)
The "Average" group is the geometric mean for speedup and the arithmetic mean
for every other metric.

Usage: python3 scripts/task1b_metrics.py [folder] [--configs baseline,ip_stride,spp]
                                         [--labels "No prefetching,IP-stride,SPP"]
  folder     default results/task1b
  --configs  configs to include, baseline first (default: every folder found)
  --labels   names shown in the tables and plots, same order as --configs
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

BASELINE = "baseline"
KNOWN_LABELS = {"baseline": "No prefetching", "ip_stride": "IP-stride",
                "spp": "SPP", "spp_small": "SPP (small)", "spp2": "SPP2"}
KNOWN_ORDER = ["baseline", "ip_stride", "spp", "spp_small", "spp2"]

# Same palette and styling as scripts/plot_results.py
COLORS = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300"]
INK, MUTED, GRID = "#2C2C2A", "#5F5E5A", "#D3D1C7"

RE_IPC = re.compile(r"^CPU 0 cumulative IPC:\s*(\S+)", re.M)
RE_L1D_LOAD = re.compile(r"^L1D LOAD\s+ACCESS:\s*(\d+)\s+HIT:\s*(\d+)\s+MISS:\s*(\d+).*MPKI:\s*(\S+)", re.M)
RE_L1D_PF = re.compile(r"^L1D USEFUL LOAD PREFETCHES:\s*(\d+)\s+PREFETCH ISSUED TO LOWER LEVEL:\s*(\d+)"
                       r"\s+ACCURACY:\s*(\S+)", re.M)


def parse(path):
    """Region of Interest stats of one run, or None if the run did not finish."""
    with open(path, errors="replace") as f:
        text = f.read()
    start = text.find("Region of Interest Statistics")
    if start < 0:
        return None
    roi = text[start:]
    ipc, load, pf = RE_IPC.search(roi), RE_L1D_LOAD.search(roi), RE_L1D_PF.search(roi)
    if not (ipc and load and pf):
        return None
    accuracy = float(pf.group(3))           # "-nan" when nothing was issued
    return {"ipc": float(ipc.group(1)),
            "l1d_load_access": int(load.group(1)),
            "l1d_load_miss": int(load.group(3)),
            "l1d_mpki": float(load.group(4)),
            "pf_useful": int(pf.group(1)),
            "pf_issued": int(pf.group(2)),
            "accuracy": accuracy if not math.isnan(accuracy) else float("nan")}


def geomean(xs):
    xs = [x for x in xs if x > 0 and not math.isnan(x)]
    return math.exp(sum(map(math.log, xs)) / len(xs)) if xs else float("nan")


def mean(xs):
    xs = [x for x in xs if not math.isnan(x)]
    return sum(xs) / len(xs) if xs else float("nan")


def fmt(x, digits):
    return "-" if x is None or math.isnan(x) else f"{x:.{digits}f}"


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


def grouped_bars(ax, data, groups, configs, labels, colors, key, base=0.0, digits=2):
    """One group of bars per trace (+ Average), one bar per config, value on top."""
    width = 0.8 / len(configs)
    for i, (config, label) in enumerate(zip(configs, labels)):
        xs, values = [], []
        for g, group in enumerate(groups):
            v = data.get((config, group), {}).get(key, float("nan"))
            if not math.isnan(v):
                xs.append(g - 0.4 + width * (i + 0.5))
                values.append(v)
        ax.bar(xs, [v - base for v in values], width * 0.9, bottom=base,
               color=colors[i], label=label, zorder=3)
        for x, v in zip(xs, values):
            ax.text(x, v, fmt(v, digits), ha="center", va="bottom" if v >= base else "top",
                    fontsize=6.5, color=INK)
    ax.set_xticks(range(len(groups)))
    ax.set_xticklabels(groups)
    low, high = ax.get_ylim()
    ax.set_ylim(low, high + (high - low) * 0.18)          # room for value labels and legend


def save(fig, ax, path, ncol):
    ax.legend(fontsize=8, frameon=False, ncol=ncol, loc="upper left")
    fig.tight_layout()
    fig.savefig(path, dpi=200)
    plt.close(fig)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("folder", nargs="?", default="results/task1b")
    ap.add_argument("--configs", help="comma separated, baseline first")
    ap.add_argument("--labels", help="comma separated, same order as --configs")
    args = ap.parse_args()

    if args.configs:
        configs = args.configs.split(",")
    else:
        found = [d for d in os.listdir(args.folder) if os.path.isdir(os.path.join(args.folder, d))
                 and any(f.endswith(".txt") for f in os.listdir(os.path.join(args.folder, d)))]
        configs = sorted(found, key=lambda c: (KNOWN_ORDER.index(c) if c in KNOWN_ORDER else len(KNOWN_ORDER), c))
    if BASELINE not in configs:
        sys.exit(f"[task1b] no '{BASELINE}' folder in {args.folder}: needed for speedup and coverage")
    configs.remove(BASELINE)
    configs.insert(0, BASELINE)
    labels = args.labels.split(",") if args.labels else [KNOWN_LABELS.get(c, c) for c in configs]
    if len(labels) != len(configs):
        sys.exit("[task1b] --labels must name every config in --configs")
    colors = {c: COLORS[i % len(COLORS)] for i, c in enumerate(configs)}

    # ---- parse ----
    raw = {}
    for config in configs:
        folder = os.path.join(args.folder, config)
        for name in sorted(os.listdir(folder)):
            if name.endswith(".txt"):
                stats = parse(os.path.join(folder, name))
                if stats is None:
                    print(f"[task1b] skipping unfinished run {folder}/{name}", file=sys.stderr)
                else:
                    raw[(config, name[:-4])] = stats
    traces = sorted({t for c, t in raw if c == BASELINE})
    for config in configs:
        missing = [t for t in traces if (config, t) not in raw]
        if missing:
            print(f"[task1b] {config}: no finished run for {', '.join(missing)}", file=sys.stderr)
    if not traces:
        sys.exit("[task1b] no finished baseline runs")

    # ---- metrics ----
    data = {}
    for (config, trace), r in raw.items():
        if trace not in traces:
            continue
        base = raw[(BASELINE, trace)]
        is_base = config == BASELINE
        data[(config, trace)] = dict(
            r,
            speedup=r["ipc"] / base["ipc"],
            accuracy=float("nan") if is_base else r["accuracy"],
            coverage=float("nan") if is_base or not base["l1d_load_miss"] else
            100.0 * (base["l1d_load_miss"] - r["l1d_load_miss"]) / base["l1d_load_miss"])
    for config in configs:
        rows = [data[(config, t)] for t in traces if (config, t) in data]
        data[(config, "Average")] = {
            "speedup": geomean([r["speedup"] for r in rows]),
            **{k: mean([r[k] for r in rows]) for k in ("ipc", "l1d_mpki", "accuracy", "coverage")}}

    # ---- CSV ----
    groups = traces + ["Average"]
    fields = ["trace", "config", "ipc", "speedup", "l1d_mpki", "accuracy", "coverage",
              "l1d_load_access", "l1d_load_miss", "pf_issued", "pf_useful"]
    csv_path = os.path.join(args.folder, "task1b_metrics.csv")
    with open(csv_path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(fields)
        for trace in groups:
            for config in configs:
                r = data.get((config, trace))
                if r:
                    w.writerow([trace, config] + [
                        "" if isinstance(r.get(k), float) and math.isnan(r[k]) else
                        (f"{r[k]:.6f}" if isinstance(r.get(k), float) else r.get(k, ""))
                        for k in fields[2:]])

    # ---- markdown tables (one per metric: rows = traces, columns = configs) ----
    pf_configs = configs[1:]
    pf_labels = labels[1:]
    tables = [("IPC", "ipc", configs, labels, 4),
              ("Speedup over no prefetching (Average = geometric mean)", "speedup", pf_configs, pf_labels, 4),
              ("L1D load MPKI", "l1d_mpki", configs, labels, 3),
              ("L1D prefetch accuracy (%)", "accuracy", pf_configs, pf_labels, 2),
              ("L1D prefetch coverage (%)", "coverage", pf_configs, pf_labels, 2)]
    lines = ["# Task 1B results", ""]
    for title, key, cfgs, labs, digits in tables:
        lines += [f"## {title}", "", "| Trace | " + " | ".join(labs) + " |",
                  "|---|" + "---:|" * len(cfgs)]
        for g in groups:
            name = "**Average**" if g == "Average" else g
            lines.append(f"| {name} | " + " | ".join(
                fmt(data.get((c, g), {}).get(key, float("nan")), digits) for c in cfgs) + " |")
        lines.append("")
    md_path = os.path.join(args.folder, "task1b_table.md")
    with open(md_path, "w") as f:
        f.write("\n".join(lines))
    print("\n".join(lines))

    # ---- plots ----
    out = os.path.join(args.folder, "plots")
    os.makedirs(out, exist_ok=True)
    pf_colors = [colors[c] for c in pf_configs]
    all_colors = [colors[c] for c in configs]

    fig, ax = plt.subplots(figsize=(7.5, 3.8))
    grouped_bars(ax, data, groups, pf_configs, pf_labels, pf_colors, "speedup", base=1.0, digits=4)
    ax.axhline(1.0, color=colors[BASELINE], lw=1.2, ls="--", zorder=4, label=f"{labels[0]} (baseline)")
    style(ax, "Speedup over no prefetching (higher is better)", "speedup")
    save(fig, ax, os.path.join(out, "speedup.png"), ncol=len(configs))

    fig, ax = plt.subplots(figsize=(7.5, 3.8))
    grouped_bars(ax, data, groups, configs, labels, all_colors, "l1d_mpki", digits=2)
    style(ax, "L1D load MPKI (lower is better)", "load misses / 1000 instructions")
    save(fig, ax, os.path.join(out, "mpki.png"), ncol=len(configs))

    fig, ax = plt.subplots(figsize=(7.5, 3.8))
    grouped_bars(ax, data, groups, pf_configs, pf_labels, pf_colors, "accuracy", digits=1)
    style(ax, "L1D prefetch accuracy (higher is better)", "useful / issued prefetches (%)")
    save(fig, ax, os.path.join(out, "accuracy.png"), ncol=len(pf_configs))

    fig, ax = plt.subplots(figsize=(7.5, 3.8))
    grouped_bars(ax, data, groups, pf_configs, pf_labels, pf_colors, "coverage", digits=1)
    ax.axhline(0, color=MUTED, lw=0.8, zorder=4)
    style(ax, "L1D prefetch coverage (higher is better)", "baseline load misses removed (%)")
    save(fig, ax, os.path.join(out, "coverage.png"), ncol=len(pf_configs))

    fig, ax = plt.subplots(figsize=(7.5, 3.8))
    grouped_bars(ax, data, groups, configs, labels, all_colors, "ipc", digits=3)
    style(ax, "IPC (higher is better)", "instructions per cycle")
    save(fig, ax, os.path.join(out, "ipc.png"), ncol=len(configs))

    print(f"[task1b] wrote {csv_path}, {md_path}")
    print(f"[task1b] wrote speedup.png, mpki.png, accuracy.png, coverage.png, ipc.png in {out}/")


if __name__ == "__main__":
    main()
