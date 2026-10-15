#!/usr/bin/env python3
"""Task 1B: metrics tables and plots for baseline, IP-stride, SPP and the SPP throttle sweep.

Reads   <folder>/baseline/<trace>.txt        no L1D prefetching
        <folder>/ip_stride/<trace>.txt       IP-stride prefetcher
        <folder>/spp/<trace>.txt             SPP prefetcher
        <folder>/throttle_test/spp_<MIN_CONF>_<MAX_CONF>_deg_<MAX_DEGREE>.txt
                                             SPP with other accuracy thresholds / max degree
                                             (the older "acc_" prefix is accepted too)
Writes  <folder>/task1b_metrics.csv          every metric, per trace and config
        <folder>/task1b_throttle.csv         every metric, per throttle setting
        <folder>/task1b_table.md             all tables in markdown for the report
        <folder>/plots/speedup.png           speedup over the baseline
        <folder>/plots/mpki.png              L1D load MPKI
        <folder>/plots/accuracy.png          L1D prefetch accuracy
        <folder>/plots/coverage.png          L1D prefetch coverage
        <folder>/plots/ipc.png               IPC
        <folder>/plots/throttle_thresholds.png  sweep over (MIN_CONF, MAX_CONF) at a fixed degree
        <folder>/plots/throttle_degree.png      sweep over MAX_DEGREE at fixed thresholds

Metrics (Region of Interest statistics, as defined in the assignment):
  IPC        CPU 0 cumulative IPC
  Speedup    IPC with prefetcher / IPC of baseline (no prefetching)
  L1D MPKI   MPKI of the "L1D LOAD" line
  Accuracy   ACCURACY of the "L1D USEFUL LOAD PREFETCHES" line
             (useful load prefetches / prefetches issued to lower level, %)
  Coverage   (baseline L1D load misses - L1D load misses) / baseline L1D load misses (%)
The "Average" group is the geometric mean for speedup and the arithmetic mean
for every other metric.

Each throttle run is compared against the baseline run of the same trace, found
from the "CPU 0 runs <path>" line of its output (or forced with --throttle-trace).
Accuracy thresholds: below MIN_CONF the degree goes down, above MAX_CONF it goes up,
up to MAX_DEGREE.

Usage: python3 scripts/task1b_metrics.py [folder] [--throttle-trace Trace1-003]
  folder            default results/task1b
  --throttle-trace  baseline trace to compare every throttle run against
"""
import argparse
import csv
import math
import os
import re
import sys
from collections import Counter
import matplotlib
matplotlib.use("Agg")                       # draw to files, no window
import matplotlib.pyplot as plt

BASELINE = "baseline"
CONFIGS = ["baseline", "ip_stride", "spp"]
LABELS = {"baseline": "No prefetching", "ip_stride": "IP-stride", "spp": "SPP"}
THROTTLE_DIR = "throttle_test"
RE_THROTTLE = re.compile(r"^(?:spp|acc)_([\d.]+)_([\d.]+)_deg_(\d+)\.txt$")

# Same palette and styling as scripts/plot_results.py
COLORS = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300"]
INK, MUTED, GRID = "#2C2C2A", "#5F5E5A", "#D3D1C7"
CONFIG_COLORS = dict(zip(CONFIGS, COLORS))
SWEEP_COLOR = COLORS[3]

RE_IPC = re.compile(r"^CPU 0 cumulative IPC:\s*(\S+)", re.M)
RE_L1D_LOAD = re.compile(r"^L1D LOAD\s+ACCESS:\s*(\d+)\s+HIT:\s*(\d+)\s+MISS:\s*(\d+).*MPKI:\s*(\S+)", re.M)
RE_L1D_PF = re.compile(r"^L1D USEFUL LOAD PREFETCHES:\s*(\d+)\s+PREFETCH ISSUED TO LOWER LEVEL:\s*(\d+)"
                       r"\s+ACCURACY:\s*(\S+)", re.M)
RE_TRACE = re.compile(r"^CPU 0 runs\s+(\S+)", re.M)

# (title, key, digits, axis label) for every metric of the deliverables
METRICS = [("IPC", "ipc", 4, "instructions per cycle"),
           ("Speedup over no prefetching", "speedup", 4, "speedup"),
           ("L1D load MPKI", "l1d_mpki", 3, "load misses / 1000 instructions"),
           ("L1D prefetch accuracy (%)", "accuracy", 2, "useful / issued prefetches (%)"),
           ("L1D prefetch coverage (%)", "coverage", 2, "baseline load misses removed (%)")]
NAN = float("nan")


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
    trace = RE_TRACE.search(text)
    accuracy = float(pf.group(3))           # already %, "-nan" when nothing was issued
    return {"ipc": float(ipc.group(1)),
            "l1d_load_access": int(load.group(1)),
            "l1d_load_miss": int(load.group(3)),
            "l1d_mpki": float(load.group(4)),
            "pf_useful": int(pf.group(1)),
            "pf_issued": int(pf.group(2)),
            "accuracy": accuracy,
            "trace_path": trace.group(1) if trace else ""}


def derive(r, base, is_base=False):
    """Speedup and coverage of run r against its baseline run."""
    return dict(
        r,
        speedup=r["ipc"] / base["ipc"],
        accuracy=NAN if is_base else r["accuracy"],
        coverage=NAN if is_base or not base["l1d_load_miss"] else
        100.0 * (base["l1d_load_miss"] - r["l1d_load_miss"]) / base["l1d_load_miss"])


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


def grouped_bars(ax, data, groups, configs, key, base=0.0, digits=2):
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


def sweep_figure(rows, xlabels, refs, title, path):
    """2x2 panels (speedup, MPKI, accuracy, coverage), one bar per throttle setting.
    refs: {label: stats} drawn as dashed reference lines (IP-stride / SPP on the same trace)."""
    fig, axes = plt.subplots(2, 2, figsize=(9, 6))
    panels = [("Speedup (higher is better)", "speedup", 4, 1.0),
              ("L1D load MPKI (lower is better)", "l1d_mpki", 2, 0.0),
              ("L1D prefetch accuracy % (higher is better)", "accuracy", 1, 0.0),
              ("L1D prefetch coverage % (higher is better)", "coverage", 1, 0.0)]
    for ax, (ptitle, key, digits, base) in zip(axes.flat, panels):
        values = [r[key] for r in rows]
        xs = range(len(rows))
        ax.bar(xs, [v - base for v in values], 0.6, bottom=base, color=SWEEP_COLOR, zorder=3)
        for x, v in zip(xs, values):
            if not math.isnan(v):
                ax.text(x, v, fmt(v, digits), ha="center", va="bottom" if v >= base else "top",
                        fontsize=7, color=INK)
        for (label, r), color in zip(refs.items(), [CONFIG_COLORS["ip_stride"], CONFIG_COLORS["spp"]]):
            if not math.isnan(r[key]):
                ax.axhline(r[key], color=color, lw=1.1, ls="--", zorder=4, label=f"{label} ({fmt(r[key], digits)})")
        if base:
            ax.axhline(base, color=CONFIG_COLORS[BASELINE], lw=0.8, zorder=4)
        ax.set_xticks(list(xs))
        ax.set_xticklabels(xlabels)
        style(ax, ptitle, "")
        finite = [v for v in values + [r[key] for r in refs.values()] if not math.isnan(v)]
        if finite:
            low, high = min(finite + [base]), max(finite + [base])
            pad = (high - low) * 0.25 or 0.05
            ax.set_ylim(low - pad * 0.3 if low < base else base, high + pad)
        ax.legend(fontsize=7, frameon=False, loc="upper left")
    fig.suptitle(title, fontsize=11, color=INK, fontweight="bold", x=0.01, ha="left")
    fig.tight_layout()
    fig.savefig(path, dpi=200)
    plt.close(fig)


def md_table(title, header, rows):
    return [f"## {title}", "", "| " + " | ".join(header) + " |",
            "|---|" + "---:|" * (len(header) - 1)] + ["| " + " | ".join(r) + " |" for r in rows] + [""]


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("folder", nargs="?", default="results/task1b")
    ap.add_argument("--throttle-trace", help="baseline trace name every throttle run is compared against")
    args = ap.parse_args()

    # ---- parse baseline / ip_stride / spp ----
    raw = {}
    for config in CONFIGS:
        folder = os.path.join(args.folder, config)
        if not os.path.isdir(folder):
            sys.exit(f"[task1b] missing folder {folder}")
        for name in sorted(os.listdir(folder)):
            if name.endswith(".txt"):
                stats = parse(os.path.join(folder, name))
                if stats is None:
                    print(f"[task1b] skipping unfinished run {folder}/{name}", file=sys.stderr)
                else:
                    raw[(config, name[:-4])] = stats
    traces = sorted({t for c, t in raw if c == BASELINE})
    if not traces:
        sys.exit("[task1b] no finished baseline runs")
    for config in CONFIGS:
        missing = [t for t in traces if (config, t) not in raw]
        if missing:
            print(f"[task1b] {config}: no finished run for {', '.join(missing)}", file=sys.stderr)

    # ---- metrics ----
    data = {}
    for (config, trace), r in raw.items():
        if trace in traces:
            data[(config, trace)] = derive(r, raw[(BASELINE, trace)], config == BASELINE)
    for config in CONFIGS:
        rows = [data[(config, t)] for t in traces if (config, t) in data]
        data[(config, "Average")] = {
            "speedup": geomean([r["speedup"] for r in rows]),
            **{k: mean([r[k] for r in rows]) for k in ("ipc", "l1d_mpki", "accuracy", "coverage")}}
    groups = traces + ["Average"]

    # ---- parse throttle sweep ----
    throttle = []                                         # (min_conf, max_conf, degree, trace, stats)
    tdir = os.path.join(args.folder, THROTTLE_DIR)
    names = sorted(os.listdir(tdir)) if os.path.isdir(tdir) else []
    for name in names:
        m = RE_THROTTLE.match(name)
        if not m:
            if name.endswith(".txt"):
                print(f"[task1b] {THROTTLE_DIR}/{name}: name not spp_<MIN>_<MAX>_deg_<D>.txt, skipped",
                      file=sys.stderr)
            continue
        stats = parse(os.path.join(tdir, name))
        if stats is None:
            print(f"[task1b] skipping unfinished run {tdir}/{name}", file=sys.stderr)
            continue
        if args.throttle_trace:
            trace = args.throttle_trace
        else:                                             # "/x/Trace1.gz" -> baseline "Trace1-003"
            stem = os.path.basename(stats["trace_path"]).split(".")[0]
            match = [t for t in traces if t == stem or t.startswith(stem + "-")]
            trace = match[0] if len(match) == 1 else None
        if trace not in traces:
            print(f"[task1b] {THROTTLE_DIR}/{name}: no baseline run for its trace "
                  f"'{stats['trace_path']}' (use --throttle-trace), skipped", file=sys.stderr)
            continue
        throttle.append((float(m.group(1)), float(m.group(2)), int(m.group(3)), trace,
                         derive(stats, raw[(BASELINE, trace)])))
    throttle.sort(key=lambda t: (t[3], t[0], t[1], t[2]))

    # ---- CSV ----
    fields = ["ipc", "speedup", "l1d_mpki", "accuracy", "coverage",
              "l1d_load_access", "l1d_load_miss", "pf_issued", "pf_useful"]
    csv_path = os.path.join(args.folder, "task1b_metrics.csv")
    with open(csv_path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["trace", "config"] + fields)
        for trace in groups:
            for config in CONFIGS:
                r = data.get((config, trace))
                if r:
                    w.writerow([trace, config] + [csv_value(r.get(k, "")) for k in fields])
    throttle_csv = os.path.join(args.folder, "task1b_throttle.csv")
    if throttle:
        with open(throttle_csv, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["trace", "min_conf", "max_conf", "max_degree"] + fields)
            for lo, hi, deg, trace, r in throttle:
                w.writerow([trace, lo, hi, deg] + [csv_value(r[k]) for k in fields])

    # ---- markdown tables ----
    lines = ["# Task 1B results", ""]
    for title, key, digits, _ in METRICS:
        cfgs = CONFIGS if key in ("ipc", "l1d_mpki") else CONFIGS[1:]
        if key == "speedup":
            title += " (Average = geometric mean)"
        lines += md_table(title, ["Trace"] + [LABELS[c] for c in cfgs], [
            ["**Average**" if g == "Average" else g] +
            [fmt(data.get((c, g), {}).get(key, NAN), digits) for c in cfgs] for g in groups])

    if throttle:
        lines += ["# SPP accuracy-throttling sweep", "",
                  "MIN_CONF / MAX_CONF: accuracy below / above which the prefetch degree is "
                  "decreased / increased; MAX_DEGREE: upper bound of the degree. "
                  "Each run is compared with the no-prefetching baseline on the same trace.", ""]
        rows = []
        for lo, hi, deg, trace, r in throttle:
            rows.append([trace, f"{lo:g}", f"{hi:g}", str(deg)] +
                        [fmt(r[k], d) for _, k, d, _ in METRICS] + [str(r["pf_issued"]), str(r["pf_useful"])])
        for trace in sorted({t[3] for t in throttle}):
            for config in CONFIGS[1:]:
                r = data.get((config, trace))
                if r:
                    rows.append([trace, f"*{LABELS[config]} (main run)*", "", ""] +
                                [fmt(r[k], d) for _, k, d, _ in METRICS] +
                                [str(r["pf_issued"]), str(r["pf_useful"])])
        lines += md_table("All throttle settings",
                          ["Trace", "MIN_CONF", "MAX_CONF", "MAX_DEGREE", "IPC", "Speedup", "L1D MPKI",
                           "Accuracy (%)", "Coverage (%)", "PF issued", "PF useful"], rows)
        best = max(throttle, key=lambda t: t[4]["speedup"])
        lines += [f"Best setting by speedup: MIN_CONF={best[0]:g}, MAX_CONF={best[1]:g}, "
                  f"MAX_DEGREE={best[2]} on {best[3]} (speedup {best[4]['speedup']:.4f}).", ""]

    md_path = os.path.join(args.folder, "task1b_table.md")
    with open(md_path, "w") as f:
        f.write("\n".join(lines))
    print("\n".join(lines))

    # ---- plots: baseline / ip_stride / spp ----
    out = os.path.join(args.folder, "plots")
    os.makedirs(out, exist_ok=True)
    pf = CONFIGS[1:]

    fig, ax = plt.subplots(figsize=(7.5, 3.8))
    grouped_bars(ax, data, groups, pf, "speedup", base=1.0, digits=4)
    ax.axhline(1.0, color=CONFIG_COLORS[BASELINE], lw=1.2, ls="--", zorder=4,
               label=f"{LABELS[BASELINE]} (baseline)")
    style(ax, "Speedup over no prefetching (higher is better)", "speedup")
    save(fig, ax, os.path.join(out, "speedup.png"), ncol=len(CONFIGS))

    for key, digits, title, ylabel, cfgs in [
            ("l1d_mpki", 2, "L1D load MPKI (lower is better)", METRICS[2][3], CONFIGS),
            ("accuracy", 1, "L1D prefetch accuracy (higher is better)", METRICS[3][3], pf),
            ("coverage", 1, "L1D prefetch coverage (higher is better)", METRICS[4][3], pf),
            ("ipc", 3, "IPC (higher is better)", METRICS[0][3], CONFIGS)]:
        fig, ax = plt.subplots(figsize=(7.5, 3.8))
        grouped_bars(ax, data, groups, cfgs, key, digits=digits)
        if key == "coverage":
            ax.axhline(0, color=MUTED, lw=0.8, zorder=4)
        style(ax, title, ylabel)
        save(fig, ax, os.path.join(out, {"l1d_mpki": "mpki"}.get(key, key) + ".png"), ncol=len(cfgs))
    written = ["speedup.png", "mpki.png", "accuracy.png", "coverage.png", "ipc.png"]

    # ---- plots: throttle sweep ----
    # Two one-dimensional sweeps: thresholds at the most common degree, degree at the
    # most common threshold pair. Settings outside both sweeps are only in the table.
    for trace in sorted({t[3] for t in throttle}):
        runs = [t for t in throttle if t[3] == trace]
        refs = {f"{LABELS[c]} main run": data[(c, trace)] for c in pf if (c, trace) in data}
        suffix = "" if len({t[3] for t in throttle}) == 1 else f"_{trace}"
        deg = Counter(t[2] for t in runs).most_common(1)[0][0]
        pair = Counter((t[0], t[1]) for t in runs).most_common(1)[0][0]
        by_thr = [t for t in runs if t[2] == deg]
        by_deg = sorted((t for t in runs if (t[0], t[1]) == pair), key=lambda t: t[2])
        if len(by_thr) > 1:
            name = f"throttle_thresholds{suffix}.png"
            sweep_figure([t[4] for t in by_thr], [f"{t[0]:g} / {t[1]:g}" for t in by_thr], refs,
                         f"SPP throttle thresholds MIN_CONF / MAX_CONF (MAX_DEGREE = {deg}, {trace})",
                         os.path.join(out, name))
            written.append(name)
        if len(by_deg) > 1:
            name = f"throttle_degree{suffix}.png"
            sweep_figure([t[4] for t in by_deg], [f"deg {t[2]}" for t in by_deg], refs,
                         f"SPP MAX_DEGREE (MIN_CONF / MAX_CONF = {pair[0]:g} / {pair[1]:g}, {trace})",
                         os.path.join(out, name))
            written.append(name)

    print(f"[task1b] wrote {csv_path}, {md_path}" + (f", {throttle_csv}" if throttle else ""))
    print(f"[task1b] wrote {', '.join(written)} in {out}/")


if __name__ == "__main__":
    main()
