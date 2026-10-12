"""Experimentos con cuotas fijas y repeticiones independientes (PostgreSQL 18.6)."""
import csv
import datetime as dt
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import re
import shlex
import statistics
import subprocess

ROOT = Path(__file__).resolve().parents[1]
SMOKE = os.getenv("BENCH_SMOKE", "0") == "1"
SIZES = [int(x) for x in os.getenv("N", os.getenv("SIZES", "100000 500000 1000000")).split()]
REPS = int(os.getenv("REPS", "5"))
CLIENTS = int(os.getenv("CLIENTS", "4"))
FILL = int(os.getenv("FILL", "80"))
BASE_SEED = int(os.getenv("BENCH_SEED", "42000"))
EQ = int(os.getenv("EQ_QUERIES", "10000"))
RANGE = int(os.getenv("RANGE_QUERIES", "1000"))
PSQL = shlex.split(os.environ["PSQL"]) + ["-v", "ON_ERROR_STOP=1"]
PGBENCH = shlex.split(os.environ["PGBENCH"])
DB = os.environ["PGB_DB"]
WORKLOADS = os.getenv("WORKLOADS", str(ROOT / "workloads"))
DATASETS_DIR = os.getenv("DATASETS_DIR", str(ROOT / "datasets"))
DATASETS = os.getenv("DATASETS", "d1 d2 d3").split()
CONFIGS = os.getenv("CONFIGS", "none btree isam").split()
stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%d_%H%M%S")
OUT = Path(os.getenv("OUT", str(ROOT / "benchmarks/results" / f"bench_corrected_{stamp}.csv")))
LOGS = OUT.with_suffix("").with_name(OUT.stem + "_logs")

def run(args, **kwargs):
    result = subprocess.run(args, text=True, capture_output=True,
                            env={**os.environ, "LC_ALL": "C"}, **kwargs)
    if result.returncode:
        raise RuntimeError(f"Comando falló (exit={result.returncode}):\n{result.stdout}\n{result.stderr}")
    return result.stdout

def sql(query):
    return run(PSQL + ["-c", query]).strip()

def metric(pattern, output):
    m = re.search(pattern, output, re.M)
    if not m:
        raise RuntimeError(f"Métrica ausente: {pattern}\n{output}")
    return m.group(1)

def buffers(predicate):
    plan = sql(f"EXPLAIN (ANALYZE, BUFFERS, TIMING OFF) SELECT count(payload) FROM bench WHERE {predicate}")
    for line in plan.splitlines():
        if "Buffers:" in line:
            return sum(int(v) for v in re.findall(r"=(\d+)", line))
    return 0

def fingerprint_inserted():
    return sql("SELECT md5(coalesce(string_agg(id::text || ':' || c::text, ',' ORDER BY id),'')) "
               "FROM (SELECT id,count(*) c FROM bench WHERE payload=repeat('i',40) GROUP BY id) s")

def main():
    if not SMOKE and (any(n not in (100000, 500000, 1000000) for n in SIZES) or REPS < 5 or EQ < 10000 or RANGE < 1000):
        raise ValueError("Experimento oficial: tamaños 100k/500k/1M, REPS>=5, EQ>=10000, RANGE>=1000. BENCH_SMOKE=1 permite diagnóstico explícito.")
    if min(SIZES + [CLIENTS, REPS, EQ, RANGE]) <= 0 or any(n < 10 for n in SIZES):
        raise ValueError("Los tamaños y cuotas deben ser positivos (N>=10)")
    if not 10 <= FILL <= 100:
        raise ValueError("FILL debe estar entre 10 y 100")
    if not set(DATASETS) <= {"d1", "d2", "d3"} or not set(CONFIGS) <= {"none", "btree", "isam"}:
        raise ValueError("Dataset/configuración desconocidos")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    LOGS.mkdir(parents=True, exist_ok=True)
    if OUT.exists():
        raise FileExistsError(f"No sobrescribir resultados existentes: {OUT}")
    version = sql("SHOW server_version_num")
    if version != "180006":
        raise RuntimeError(f"Se requiere PostgreSQL 18.6, encontrado {version}")
    # Igual configuración del executor en cada conexión, incluido pgbench.
    sql(f'ALTER DATABASE "{DB}" SET max_parallel_workers_per_gather=0')
    sql(f'ALTER DATABASE "{DB}" SET jit=off')
    metadata = {
        "schema": 2, "started_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "status": "running", "smoke": SMOKE, "sizes": SIZES, "reps": REPS,
        "datasets": DATASETS, "configs": CONFIGS, "clients": CLIENTS,
        "eq_queries": EQ, "range_queries": RANGE, "inserts": "N/10",
        "seed_base": BASE_SEED, "data_seed": 0.42, "zipf_parameter": 1.1,
        "fill_pct": FILL, "maintenance_workers": 0,
        "version": sql("SELECT version()"), "settings": sql("SELECT name || '=' || setting FROM pg_settings WHERE name IN ('shared_buffers','work_mem','maintenance_work_mem','max_parallel_workers_per_gather','jit','fsync','synchronous_commit','full_page_writes') ORDER BY name"),
        "host_platform": platform.platform(), "host_cpus": os.cpu_count(),
        "memory": Path('/proc/meminfo').read_text().splitlines()[0],
        "cache_protocol": "Datos recién cargados y leídos para validar unicidad; VACUUM ANALYZE antes de cada repetición. Sin vaciado artificial de caché.",
        "file_sha256": {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for directory in ("datasets", "workloads", "isam_am", "benchmarks") for p in (ROOT/directory).rglob('*') if p.is_file() and p.suffix in ('.sql','.pgb','.c','.h','.py','.sh')},
    }
    meta_path = OUT.with_suffix('.json')
    meta_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2))
    fields = ['dataset','n','config','workload','rep','tps','lat_ms','build_ms','index_bytes','buffers_eq','buffers_range','overflow_blocks','longest_chain','seed','transactions','failed_transactions','rows_after','insert_fingerprint']
    expected_inserts = {}
    with OUT.open('x', newline='') as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader(); fh.flush()
        for n in SIZES:
            for ds in DATASETS:
                for rep in range(1, REPS+1):
                    seed = BASE_SEED + rep
                    for cfg in CONFIGS:
                        prefix = f"{ds}_{n}_{cfg}_r{rep}"
                        print(f">> {prefix}: carga independiente", flush=True)
                        run(PSQL + ['-v',f'n={n}','-v',f'allow_smoke={str(SMOKE).lower()}', '-f', str(Path(DATASETS_DIR)/f'{ds}.sql')])
                        valid = sql('SELECT count(*) || \'/\' || count(DISTINCT id) || \'/\' || min(id) || \'/\' || max(id) FROM bench')
                        if valid != f'{n}/{n}/1/{n}':
                            raise RuntimeError(f'Dataset inválido: {valid}')
                        build = '0'
                        if cfg != 'none':
                            statement = 'CREATE INDEX bench_idx ON bench (id)' if cfg=='btree' else 'CREATE INDEX bench_idx ON bench USING isam_am(id)'
                            output = run(PSQL, input=f'\\timing on\nSET max_parallel_maintenance_workers=0;\nSET isam_am.fill_pct={FILL};\n{statement};\n')
                            (LOGS/f'{prefix}_build.log').write_text(output)
                            build = re.findall(r'^Time: ([0-9.]+) ms',output,re.M)[-1]
                        sql('VACUUM ANALYZE bench')
                        stages = [('w1_eq_uniform','w1_eq_uniform.pgb',EQ),('w2_eq_absent','w2_eq_absent.pgb',EQ),('w4_range','w4_range.pgb',RANGE),('w3_insert','w3_insert.pgb',n//10),('w1_eq_after_inserts','w1_eq_uniform.pgb',EQ),('w4_range_after_inserts','w4_range.pgb',RANGE)]
                        inserted_fp = ''
                        for wl,script,total in stages:
                            clients = math.gcd(CLIENTS,total)
                            args = PGBENCH + ['-n','-c',str(clients),'-j',str(clients),'-t',str(total//clients),'--random-seed',str(seed),'-D',f'n={n}','-D',f'dom={n}','-D',f'span={max(1,n//1000)}','-D',f'skew={int(ds=="d3")}','-f',f'{WORKLOADS}/{script}',DB]
                            output = run(args)
                            (LOGS/f'{prefix}_{wl}.log').write_text(output)
                            count = int(metric(r'^number of transactions actually processed: (\d+)',output))
                            failed = int(metric(r'^number of failed transactions: (\d+)',output))
                            if count != total or failed:
                                raise RuntimeError(f'Cuota o transacciones fallidas: {prefix}/{wl}: {count}/{failed}')
                            rows_after = int(sql('SELECT count(*) FROM bench'))
                            if rows_after != n + (n//10 if wl in ('w3_insert','w1_eq_after_inserts','w4_range_after_inserts') else 0):
                                raise RuntimeError('Número de filas inesperado')
                            if wl == 'w3_insert':
                                inserted_fp = fingerprint_inserted()
                                expected = expected_inserts.setdefault((ds,n,rep),inserted_fp)
                                if expected != inserted_fp:
                                    raise RuntimeError('Las alternativas no ejecutaron el mismo multiconjunto de inserciones')
                                sql('ANALYZE bench')
                            size = sql("SELECT coalesce(pg_relation_size(to_regclass('bench_idx')),0)")
                            ovf = sql("SELECT overflow_blocks || ',' || longest_chain FROM isam_index_stats('bench_idx')").split(',') if cfg=='isam' else ['0','0']
                            row = dict(zip(fields,[ds,n,cfg,wl,rep,metric(r'^tps = ([0-9.]+)',output),metric(r'^latency average = ([0-9.]+)',output),build,size,buffers(f'id={n//2}'),buffers(f'id BETWEEN {n//2} AND {n//2+max(1,n//1000)}'),*ovf,seed,count,failed,rows_after,inserted_fp]))
                            writer.writerow(row); fh.flush()
                            print(f"   {wl}: {count} operaciones, {row['tps']} TPS",flush=True)
    metadata['status']='completed'
    metadata['completed_utc']=dt.datetime.now(dt.timezone.utc).isoformat()
    metadata['csv_sha256']=hashlib.sha256(OUT.read_bytes()).hexdigest()
    meta_path.write_text(json.dumps(metadata,ensure_ascii=False,indent=2))
    print(f'Resultados completos: {OUT}',flush=True)

if __name__=='__main__':
    existed = OUT.exists()
    try:
        main()
    except Exception as exc:
        meta = OUT.with_suffix('.json')
        if not existed and meta.exists():
            record = json.loads(meta.read_text())
            record.update(status='failed',failure=str(exc))
            meta.write_text(json.dumps(record,ensure_ascii=False,indent=2))
        raise
