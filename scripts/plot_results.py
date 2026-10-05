#!/usr/bin/env python3
"""Draw the report plots and a markdown table from <folder>/summary.csv.

Plots (saved in <folder>/plots/):
  speedup.png   speedup over the baseline per trace + geometric mean
  ipc.png       IPC per trace
  mpki.png      L2C load / L2 instruction / L2 data MPKI per trace
  variants.png  average speedup and instruction MPKI of every configuration
Table: <folder>/table.md  (main configurations, ready for the report)

Usage: python3 scripts/plot_results.py [folder] [--main lru,rrip,irrip]
                                       [--labels LRU,SRRIP,I-RRIP]
Run scripts/parse_results.py first.
"""
import argparse
import csv
import os
import matplotlib
matplotlib.use("Agg")                       # draw to files, no window
import matplotlib.pyplot as plt

# One fixed colour per main configuration (colour-blind checked palette)
COLORS = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300"]
INK, MUTED, GRID, HIGHLIGHT, OTHER = "#2C2C2A", "#5F5E5A", "#D3D1C7", "#1baf7a", "#9ec5f4"


def read_summary(folder):
    """{(config, trace): {column: float}} from summary.csv (trace may be GEOMEAN)."""
    data = {}
    with open(os.path.join(folder, "summary.csv")) as f:
        for row in csv.DictReader(f):
            data[(row["config"], row["trace"])] = {
                k: float(v) for k, v in row.items() if k not in ("config", "trace") and v not in ("", None)}
    return data


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


def grouped_bars(ax, data, groups, configs, labels, key, base=0.0, show_values=False, colors=COLORS):
    """One group of bars per trace, one bar per configuration, starting at base."""
    width = 0.8 / len(configs)
    for i, (config, label) in enumerate(zip(configs, labels)):
        xs, values = [], []
        for g, group in enumerate(groups):
            row = data.get((config, group))
            if row and key in row:
                xs.append(g - 0.4 + width * (i + 0.5))
                values.append(row[key])
        ax.bar(xs, [v - base for v in values], width * 0.9, bottom=base,
               color=colors[i], label=label, zorder=3)
        if show_values:
            for x, v in zip(xs, values):
                ax.text(x, v, f"{v:.4f}", ha="center", va="bottom" if v >= base else "top",
                        fontsize=7, color=INK)
    ax.set_xticks(range(len(groups)))
    ax.set_xticklabels(["Average" if g == "GEOMEAN" else g for g in groups])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("folder", nargs="?", default="results/task2a")
    ap.add_argument("--main", default="lru,rrip,irrip", help="baseline first")
    ap.add_argument("--labels", default="LRU,SRRIP,I-RRIP")
    args = ap.parse_args()
    configs, labels = args.main.split(","), args.labels.split(",")
    data = read_summary(args.folder)
    traces = sorted({t for _, t in data if t != "GEOMEAN"})
    out = os.path.join(args.folder, "plots")
    os.makedirs(out, exist_ok=True)

    # 1. speedup over the baseline (bars grow up or down from the 1.0 line)
    fig, ax = plt.subplots(figsize=(7, 3.6))
    grouped_bars(ax, data, traces + ["GEOMEAN"], configs[1:], labels[1:], "speedup",
                 base=1.0, show_values=True, colors=COLORS[1:])   # same colour per policy as other plots
    low, high = ax.get_ylim()
    ax.set_ylim(low - (high - low) * 0.05, high + (high - low) * 0.25)     # room for labels and legend
    ax.axhline(1.0, color=COLORS[0], lw=1.2, ls="--", zorder=4, label=f"{labels[0]} (baseline)")
    style(ax, f"Speedup over {labels[0]} (higher is better)", "speedup")
    ax.legend(fontsize=8, frameon=False, ncol=3, loc="upper left")
    fig.tight_layout(); fig.savefig(os.path.join(out, "speedup.png"), dpi=200); plt.close(fig)

    # 2. IPC per trace
    fig, ax = plt.subplots(figsize=(7, 3.4))
    grouped_bars(ax, data, traces, configs, labels, "ipc")
    style(ax, "IPC (higher is better)", "instructions per cycle")
    ax.legend(fontsize=8, frameon=False, ncol=3, loc="upper left")
    fig.tight_layout(); fig.savefig(os.path.join(out, "ipc.png"), dpi=200); plt.close(fig)

    # 3. the three L2 MPKI values, one panel each
    fig, axes = plt.subplots(1, 3, figsize=(10, 3.4))
    panels = [("l2c_load_mpki", "L2C load MPKI"), ("l2c_instr_mpki", "L2 instruction load MPKI"),
              ("l2c_data_mpki", "L2 data load MPKI")]
    for ax, (key, title) in zip(axes, panels):
        grouped_bars(ax, data, traces, configs, labels, key)
        style(ax, title, "misses / 1000 instructions")
    axes[0].legend(fontsize=8, frameon=False, loc="upper left")
    fig.suptitle("L2 misses per kilo-instruction (lower is better)", fontsize=10, color=INK, x=0.01, ha="left")
    fig.tight_layout(); fig.savefig(os.path.join(out, "mpki.png"), dpi=200); plt.close(fig)

    # 4. all configurations: average speedup gain and instruction MPKI on the
    #    trace with the most instruction misses under the baseline
    others = [c for c in sorted({c for c, _ in data}) if c != configs[0]]
    if len(others) > len(configs) - 1:
        code_trace = max(traces, key=lambda t: data[(configs[0], t)]["l2c_instr_mpki"])
        others.sort(key=lambda c: data[(c, "GEOMEAN")]["speedup"])
        colors = [HIGHLIGHT if c == configs[-1] else OTHER for c in others]
        fig, (a1, a2) = plt.subplots(1, 2, figsize=(10, 3.6), sharey=True)
        gains = [(data[(c, "GEOMEAN")]["speedup"] - 1) * 100 for c in others]
        a1.barh(others, gains, color=colors, zorder=3)
        for y, g in enumerate(gains):
            a1.text(g, y, f" {g:.2f}%", va="center", fontsize=7.5, color=INK)
        a2.barh(others, [data[(c, code_trace)]["l2c_instr_mpki"] for c in others], color=colors, zorder=3)
        for ax, title, xlabel in ((a1, f"Average speedup over {labels[0]} (higher is better)", "% faster"),
                                  (a2, f"{code_trace}: L2 instruction MPKI (lower is better)", "misses / 1000 instr.")):
            style(ax, title, "")
            ax.grid(axis="y", visible=False); ax.grid(axis="x", color=GRID, lw=0.6, zorder=0)
            ax.set_xlabel(xlabel, fontsize=8.5, color=MUTED)
            ax.tick_params(axis="x", colors=MUTED, labelsize=8); ax.tick_params(axis="y", colors=INK, labelsize=8)
        fig.tight_layout(); fig.savefig(os.path.join(out, "variants.png"), dpi=200); plt.close(fig)

    # 5. markdown table for the report
    lines = ["| Trace | Policy | IPC | Speedup | L2C load MPKI | L2 instr MPKI | L2 data MPKI |",
             "|---|---|---|---|---|---|---|"]
    for trace in traces:
        for config, label in zip(configs, labels):
            r = data[(config, trace)]
            lines.append(f"| {trace} | {label} | {r['ipc']:.4f} | {r['speedup']:.4f} | "
                         f"{r['l2c_load_mpki']:.3f} | {r['l2c_instr_mpki']:.3f} | {r['l2c_data_mpki']:.3f} |")
    for config, label in zip(configs, labels):
        lines.append(f"| Average (geomean) | {label} |  | {data[(config, 'GEOMEAN')]['speedup']:.4f} |  |  |  |")
    with open(os.path.join(args.folder, "table.md"), "w") as f:
        f.write("\n".join(lines) + "\n")
    print(f"plots in {out}/, table in {os.path.join(args.folder, 'table.md')}")


if __name__ == "__main__":
    main()
