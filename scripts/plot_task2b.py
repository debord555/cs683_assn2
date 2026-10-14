#!/usr/bin/env python3
"""Task 2B sensitivity study: plot and table from <folder>/summary.csv.

Reads the dyn_t<threshold> configurations (made by scripts/run_task2b.sh and
collected by scripts/parse_results.py) and writes:
  <folder>/plots/sensitivity.png   speedup over the baseline vs threshold
                                   (one line per trace + geomean) and the share
                                   of follower accesses served in I-RRIP mode
  <folder>/sensitivity.md          the same numbers as a table for the report
  <folder>/leaders.md              threshold 0.25 with 16 / 32 / 64 leader sets

Usage: python3 scripts/plot_task2b.py [folder]          (default results/task2b)
Run scripts/parse_results.py first.
"""
import csv
import os
import re
import sys
import matplotlib
matplotlib.use("Agg")                       # draw to files, no window
import matplotlib.pyplot as plt

COLORS = ["#2a78d6", "#eb6834", "#1baf7a", "#2C2C2A"]   # Trace1..3, geomean
INK, MUTED, GRID = "#2C2C2A", "#5F5E5A", "#D3D1C7"


def read_summary(folder):
    """{(config, trace): {column: float}} from summary.csv."""
    data = {}
    with open(os.path.join(folder, "summary.csv")) as f:
        for row in csv.DictReader(f):
            data[(row["config"], row["trace"])] = {
                k: float(v) for k, v in row.items() if k not in ("config", "trace") and v not in ("", None)}
    return data


def style(ax, title, ylabel):
    ax.set_title(title, fontsize=10, color=INK, loc="left", fontweight="bold")
    ax.set_ylabel(ylabel, fontsize=8.5, color=MUTED)
    ax.set_xlabel("decision threshold", fontsize=8.5, color=MUTED)
    ax.tick_params(labelsize=8, colors=MUTED, length=0)
    ax.grid(color=GRID, lw=0.6, zorder=0)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)


def main():
    folder = sys.argv[1] if len(sys.argv) > 1 else "results/task2b"
    data = read_summary(folder)
    traces = sorted({t for _, t in data if t != "GEOMEAN"})

    # threshold runs are named dyn_t<value>, e.g. dyn_t0.25
    runs = sorted((float(m.group(1)), c) for c in {c for c, _ in data}
                  for m in [re.match(r"dyn_t([\d.]+)$", c)] if m)
    if not runs:
        sys.exit("no dyn_t<threshold> results found - run scripts/run_task2b.sh T first")
    xs = [t for t, _ in runs]

    # 1. plot: speedup vs threshold (left), time in I-RRIP mode vs threshold (right)
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(10, 3.6))
    for i, trace in enumerate(traces + ["GEOMEAN"]):
        ys = [data.get((c, trace), {}).get("speedup") for _, c in runs]
        pts = [(x, y) for x, y in zip(xs, ys) if y is not None]
        label = "Average (geomean)" if trace == "GEOMEAN" else trace
        a1.plot([p[0] for p in pts], [p[1] for p in pts], marker="o", ms=4,
                lw=2.2 if trace == "GEOMEAN" else 1.4, color=COLORS[i % len(COLORS)],
                ls="-" if trace == "GEOMEAN" else "--", label=label, zorder=3)
    a1.axhline(1.0, color=MUTED, lw=0.8, zorder=2)
    style(a1, "Speedup over baseline vs threshold (higher is better)", "speedup")
    a1.legend(fontsize=8, frameon=False, loc="best")
    for i, trace in enumerate(traces):
        ys = [data.get((c, trace), {}).get("dyn_irrip_pct") for _, c in runs]
        pts = [(x, y) for x, y in zip(xs, ys) if y is not None]
        a2.plot([p[0] for p in pts], [p[1] for p in pts], marker="o", ms=4, lw=1.4,
                color=COLORS[i], label=trace, zorder=3)
    a2.set_ylim(-3, 103)
    style(a2, "Follower accesses served in I-RRIP mode", "% of follower accesses")
    a2.legend(fontsize=8, frameon=False)
    os.makedirs(os.path.join(folder, "plots"), exist_ok=True)
    fig.tight_layout()
    fig.savefig(os.path.join(folder, "plots", "sensitivity.png"), dpi=200)
    plt.close(fig)

    # 2. sensitivity table
    lines = ["| Threshold | Trace | IPC | Speedup | L2C load MPKI | L2 instr MPKI | L2 data MPKI | % in I-RRIP mode | Mode switches |",
             "|---|---|---|---|---|---|---|---|---|"]
    for t, c in runs:
        for trace in traces:
            r = data.get((c, trace))
            if r:
                lines.append(f"| {t:.2f} | {trace} | {r['ipc']:.4f} | {r['speedup']:.4f} | {r['l2c_load_mpki']:.3f} | "
                             f"{r['l2c_instr_mpki']:.3f} | {r['l2c_data_mpki']:.3f} | {r.get('dyn_irrip_pct', 0):.1f} | "
                             f"{r.get('dyn_switches', 0):.0f} |")
        g = data.get((c, "GEOMEAN"))
        if g:
            lines.append(f"| {t:.2f} | Average (geomean) |  | {g['speedup']:.4f} |  |  |  |  |  |")
    with open(os.path.join(folder, "sensitivity.md"), "w") as f:
        f.write("\n".join(lines) + "\n")

    # 3. leader-set table (16 / 32 / 64 leaders, threshold 0.25)
    leader_runs = [(16, "dyn_l16"), (32, "dyn_t0.25"), (64, "dyn_l64")]
    lines = ["| Leader sets | Trace | IPC | Speedup | L2 instr MPKI | L2 data MPKI |", "|---|---|---|---|---|---|"]
    for n, c in leader_runs:
        for trace in traces + ["GEOMEAN"]:
            r = data.get((c, trace))
            if not r:
                continue
            if trace == "GEOMEAN":
                lines.append(f"| {n} | Average (geomean) |  | {r['speedup']:.4f} |  |  |")
            else:
                lines.append(f"| {n} | {trace} | {r['ipc']:.4f} | {r['speedup']:.4f} | "
                             f"{r['l2c_instr_mpki']:.3f} | {r['l2c_data_mpki']:.3f} |")
    with open(os.path.join(folder, "leaders.md"), "w") as f:
        f.write("\n".join(lines) + "\n")

    print(f"written {folder}/plots/sensitivity.png, {folder}/sensitivity.md, {folder}/leaders.md")


if __name__ == "__main__":
    main()
