import csv
import glob
import os
import statistics
import sys
from collections import defaultdict

try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
except ImportError:
    print("matplotlib no esta instalado: pip install matplotlib", file=sys.stderr)
    sys.exit(0)

COLORS = {"none": "#999999", "btree": "#1f77b4", "isam": "#d62728"}


def latest(prefix):
    files = sorted(glob.glob(os.path.join(os.path.dirname(__file__), "results", prefix + "_*.csv")))
    return files[-1] if files else None


def plot_bench(path, rows):
    out_dir = os.path.dirname(path)
    order = ["w1_eq_uniform", "w2_eq_absent", "w5_eq_skew", "w4_range", "w3_insert",
             "w1_eq_after_inserts", "w4_range_after_inserts"]
    configs = ["none", "btree", "isam"]
    by = defaultdict(list)
    for r in rows:
        by[(r["dataset"], r["workload"], r["config"])].append(float(r["tps"]))
    for ds in sorted({r["dataset"] for r in rows}):
        fig, ax = plt.subplots(figsize=(11, 4.5))
        width = 0.27
        for i, c in enumerate(configs):
            vals = [statistics.median(by[(ds, wl, c)]) if by[(ds, wl, c)] else 0 for wl in order]
            ax.bar([x + (i - 1) * width for x in range(len(order))], vals, width, label=c, color=COLORS[c])
        ax.set_yscale("log")
        ax.set_xticks(range(len(order)))
        ax.set_xticklabels(order, rotation=25, ha="right")
        ax.set_ylabel("transacciones por segundo (log)")
        ax.set_title(f"{ds}: sin indice vs B-tree vs ISAM (n = {rows[0]['n']})")
        ax.legend()
        fig.tight_layout()
        target = os.path.join(out_dir, os.path.basename(path).replace(".csv", f"_{ds}.png"))
        fig.savefig(target, dpi=130)
        plt.close(fig)
        print(target)


def plot_overflow(path, rows):
    out_dir = os.path.dirname(path)
    configs = list(dict.fromkeys(r["config"] for r in rows))
    fig, axes = plt.subplots(1, 4, figsize=(17, 4.2))
    series = [("eq_lat_ms", "latencia igualdad caliente (ms)"),
              ("buffers_eq_hot", "buffers igualdad caliente"),
              ("index_bytes", "tamano del indice (MB)"),
              ("insert_ms", "tiempo de insercion del lote (ms)")]
    for ax, (col, title) in zip(axes, series):
        for c in configs:
            pts = [r for r in rows if r["config"] == c and r["step"] != "reindex"]
            xs = [int(r["rows"]) for r in pts]
            ys = [float(r[col]) / (1048576 if col == "index_bytes" else 1) for r in pts]
            if col == "insert_ms":
                xs, ys = xs[1:], ys[1:]
            ax.plot(xs, ys, marker="o", label=c)
        ax.set_xlabel("filas insertadas (sesgadas)")
        ax.set_title(title)
        ax.grid(alpha=0.3)
    axes[0].legend()
    fig.tight_layout()
    target = path.replace(".csv", ".png")
    fig.savefig(target, dpi=130)
    plt.close(fig)
    print(target)


def main():
    paths = sys.argv[1:] or [p for p in (latest("bench"), latest("overflow")) if p]
    if not paths:
        print("No hay CSV en benchmarks/results/", file=sys.stderr)
        sys.exit(1)
    for path in paths:
        with open(path) as fh:
            rows = list(csv.DictReader(fh))
        if rows and "workload" in rows[0]:
            plot_bench(path, rows)
        elif rows and "step" in rows[0]:
            plot_overflow(path, rows)


main()
