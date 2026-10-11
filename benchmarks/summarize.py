import csv
import glob
import os
import statistics
import sys
from collections import defaultdict


def latest(prefix):
    files = sorted(glob.glob(os.path.join(os.path.dirname(__file__), "results", prefix + "_*.csv")))
    return files[-1] if files else None


def med(values):
    return statistics.median(values) if values else float("nan")


def summarize_bench(rows):
    order = ["w1_eq_uniform", "w2_eq_absent", "w5_eq_skew", "w4_range", "w3_insert",
             "w1_eq_after_inserts", "w4_range_after_inserts"]
    configs = ["none", "btree", "isam"]
    by = defaultdict(list)
    meta = {}
    for r in rows:
        by[(r["dataset"], r["workload"], r["config"])].append(r)
        meta[(r["dataset"], r["config"])] = r
    for ds in sorted({r["dataset"] for r in rows}):
        print(f"\n### {ds} (n = {rows[0]['n']})\n")
        print("| workload | none tps | btree tps | isam tps | isam/btree | btree lat ms | isam lat ms |")
        print("|---|---:|---:|---:|---:|---:|---:|")
        for wl in order:
            tps = {c: med([float(x["tps"]) for x in by[(ds, wl, c)]]) for c in configs}
            lat = {c: med([float(x["lat_ms"]) for x in by[(ds, wl, c)]]) for c in configs}
            if all(v != v for v in tps.values()):
                continue
            ratio = tps["isam"] / tps["btree"] if tps["btree"] == tps["btree"] and tps["btree"] else float("nan")
            print(f"| {wl} | {tps['none']:.0f} | {tps['btree']:.0f} | {tps['isam']:.0f} | {ratio:.2f} | {lat['btree']:.3f} | {lat['isam']:.3f} |")
        print("\n| config | build ms | indice MB inicial | indice MB tras inserts | bloques overflow | cadena max | buffers eq | buffers range |")
        print("|---|---:|---:|---:|---:|---:|---:|---:|")
        for c in configs:
            ini = by.get((ds, "w1_eq_uniform", c))
            fin = by.get((ds, "w1_eq_after_inserts", c))
            if not ini or not fin:
                continue
            m = ini[0]
            f = fin[-1]
            print(f"| {c} | {float(m['build_ms']):.1f} | {int(m['index_bytes']) / 1048576:.2f} | {int(f['index_bytes']) / 1048576:.2f} | "
                  f"{f.get('overflow_blocks', '-')} | {f.get('longest_chain', '-')} | {m['buffers_eq']} | {m['buffers_range']} |")


def summarize_overflow(rows):
    for cfg in dict.fromkeys(r["config"] for r in rows):
        print(f"\n### {cfg} ({rows[0]['dataset']}, n = {rows[0]['n']})\n")
        print("| paso | filas insertadas | insert ms | reindex ms | indice MB | bloques overflow | cadena max | overflow % | buffers eq caliente | lat eq caliente ms |")
        print("|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
        for r in rows:
            if r["config"] != cfg:
                continue
            print(f"| {r['step']} | {r['rows']} | {float(r['insert_ms']):.0f} | {float(r['reindex_ms']):.0f} | "
                  f"{int(r['index_bytes']) / 1048576:.2f} | {r['overflow_blocks']} | {r['longest_chain']} | "
                  f"{r['overflow_pct']} | {r['buffers_eq_hot']} | {r['eq_lat_ms']} |")


def main():
    paths = sys.argv[1:] or [p for p in (latest("bench"), latest("overflow")) if p]
    if not paths:
        print("No hay CSV en benchmarks/results/", file=sys.stderr)
        sys.exit(1)
    for path in paths:
        with open(path) as fh:
            rows = list(csv.DictReader(fh))
        print(f"\n## {os.path.basename(path)}")
        if rows and "workload" in rows[0]:
            summarize_bench(rows)
        elif rows and "step" in rows[0]:
            summarize_overflow(rows)


main()
