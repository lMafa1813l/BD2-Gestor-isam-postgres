"""Trayectorias independientes de overflow, relleno y REINDEX con cuotas fijas."""
import csv
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import re
from run_bench import ROOT, PSQL, PGBENCH, DB, WORKLOADS, DATASETS_DIR, run, sql, metric, buffers, fingerprint_inserted

def main():
    n = int(os.getenv('N','100000'))
    reps = int(os.getenv('REPS','5'))
    batches = int(os.getenv('BATCHES','6'))
    batch_rows = int(os.getenv('BATCH_ROWS',str(n//5)))
    queries = int(os.getenv('HOT_QUERIES','1000'))
    smoke = os.getenv('BENCH_SMOKE','0')=='1'
    if not smoke and (n not in (100000,500000,1000000) or reps<5 or queries<1000):
        raise ValueError('N oficial, al menos cinco repeticiones y 1000 consultas por medición; BENCH_SMOKE=1 solo para diagnóstico')
    if min(n,reps,batches,batch_rows,queries)<=0:
        raise ValueError('Parámetros positivos requeridos')
    dataset = os.getenv('DATASET','d1')
    mode = os.getenv('INSERT_MODE','narrow')
    if dataset not in ('d1','d2','d3') or mode not in ('narrow','dist'):
        raise ValueError('Dataset o modo inválido')
    configs = os.getenv('CONFIGS','btree isam60 isam80 isam100 isam80t25').split()
    window = min(int(os.getenv('WINDOW','100')),n)
    if window<1: raise ValueError('WINDOW debe ser positivo')
    hotlo, hotw = (max(1,min(n//2,n-window+1)),window) if mode=='narrow' else (1,max(1,n//100))
    timestamp = dt.datetime.now(dt.timezone.utc).strftime('%Y%m%d_%H%M%S')
    out = Path(os.getenv('OUT',str(ROOT/'benchmarks/results'/f'overflow_corrected_{timestamp}.csv')))
    out.parent.mkdir(parents=True,exist_ok=True)
    logs = out.with_name(out.stem+'_logs').with_suffix('')
    logs.mkdir(exist_ok=True)
    if out.exists(): raise FileExistsError(out)
    if sql('SHOW server_version_num')!='180006': raise RuntimeError('Se requiere PG 18.6')
    sql(f'ALTER DATABASE "{DB}" SET max_parallel_workers_per_gather=0')
    sql(f'ALTER DATABASE "{DB}" SET jit=off')
    metadata={'schema':2,'status':'running','smoke':smoke,'n':n,'reps':reps,'dataset':dataset,'mode':mode,'batches':batches,'batch_rows':batch_rows,'hot_queries':queries,'window':window,'version':sql('SELECT version()'),'started_utc':dt.datetime.now(dt.timezone.utc).isoformat(),'seed_base':42000,'data_seed':0.42,'insert_seed_formula':'((rep*100+batch)%10000)/10000','clients':1,'configs':configs,'fill_reindex':'Se vuelve a fijar el relleno de cada configuración antes de REINDEX'}
    metadata['settings']=sql("SELECT name || '=' || setting FROM pg_settings WHERE name IN ('shared_buffers','work_mem','maintenance_work_mem','max_parallel_workers_per_gather','jit','fsync','synchronous_commit','full_page_writes') ORDER BY name")
    metadata['input_sha256']={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [Path(__file__),ROOT/'benchmarks/run_bench.py',ROOT/'datasets'/f'{dataset}.sql',ROOT/'workloads/w6_eq_hot.pgb']}
    out.with_suffix('.json').write_text(json.dumps(metadata,ensure_ascii=False,indent=2))
    fields=['dataset','n','config','step','rows','insert_ms','reindex_ms','index_bytes','overflow_blocks','longest_chain','overflow_pct','buffers_eq_hot','eq_lat_ms','rep','seed','transactions','failed_transactions','fill_pct','insert_fingerprint','tps']
    expected = {}
    with out.open('x',newline='') as fh:
        writer=csv.DictWriter(fh,fieldnames=fields);writer.writeheader();fh.flush()
        for rep in range(1,reps+1):
            for cfg in configs:
                match=re.fullmatch(r'isam(\d+)(?:t(\d+))?',cfg)
                if cfg!='btree' and not match: raise ValueError(cfg)
                fill=int(match.group(1)) if match else 90
                threshold=int(match.group(2)) if match and match.group(2) else None
                if not 10<=fill<=100: raise ValueError('Relleno inválido')
                prefix=f'{cfg}_r{rep}'
                print(f'>> {prefix}: carga independiente {dataset}, N={n}',flush=True)
                run(PSQL+['-v',f'n={n}','-v',f'allow_smoke={str(smoke).lower()}','-f',str(Path(DATASETS_DIR)/f'{dataset}.sql')])
                index='CREATE INDEX bench_idx ON bench(id)' if cfg=='btree' else f'SET isam_am.fill_pct={fill}; CREATE INDEX bench_idx ON bench USING isam_am(id)'
                sql('SET max_parallel_maintenance_workers=0; '+index)
                sql('VACUUM ANALYZE bench')
                inserted=0
                seed=42000+rep
                def timed(statement,label):
                    text=run(PSQL,input='\\timing on\n'+statement+'\n')
                    (logs/f'{prefix}_{label}.log').write_text(text)
                    return re.findall(r'^Time: ([0-9.]+) ms',text,re.M)[-1]
                def reindex(label):
                    return timed(f'SET max_parallel_maintenance_workers=0; SET isam_am.fill_pct={fill}; REINDEX INDEX bench_idx;',label)
                def measure(step,insert_ms,reindex_ms):
                    actual=int(sql('SELECT count(*) FROM bench'))
                    if actual!=n+inserted: raise RuntimeError('Conteo incorrecto')
                    stats=sql("SELECT overflow_blocks || ',' || longest_chain || ',' || round(overflow_pct::numeric,2) FROM isam_index_stats('bench_idx')").split(',') if cfg!='btree' else ['0','0','0']
                    output=run(PGBENCH+['-n','-c','1','-j','1','-t',str(queries),'--random-seed',str(seed),'-D',f'hotlo={hotlo}','-D',f'hotw={hotw}','-f',f'{WORKLOADS}/w6_eq_hot.pgb',DB])
                    (logs/f'{prefix}_{step}_read.log').write_text(output)
                    count=int(metric(r'^number of transactions actually processed: (\d+)',output))
                    failed=int(metric(r'^number of failed transactions: (\d+)',output))
                    if count!=queries or failed: raise RuntimeError('Cuota/errores en lectura caliente')
                    fingerprint=fingerprint_inserted()
                    reference=expected.setdefault((rep,step),fingerprint)
                    if reference!=fingerprint: raise RuntimeError('Distintos datos insertados entre configuraciones')
                    row=dict(zip(fields,[dataset+'-'+mode,n,cfg,step,inserted,insert_ms,reindex_ms,sql("SELECT pg_relation_size('bench_idx')"),*stats,buffers(f'id={hotlo+hotw//2}'),metric(r'^latency average = ([0-9.]+)',output),rep,seed,count,failed,fill,fingerprint,metric(r'^tps = ([0-9.]+)',output)]))
                    writer.writerow(row);fh.flush()
                    print(f"   paso {step}: cadena {stats[1]}, latencia {row['eq_lat_ms']} ms",flush=True)
                measure('0','0','0')
                for batch in range(1,batches+1):
                    expr=f'{hotlo}+floor(random()*{hotw})::int' if mode=='narrow' else f'CASE WHEN random()<0.8 THEN 1+floor(random()*{max(1,n//100)})::int ELSE 1+floor(random()*{n})::int END'
                    value=((rep*100+batch)%10000)/10000
                    elapsed=timed(f"SELECT setseed({value}); INSERT INTO bench SELECT {expr},repeat('i',40) FROM generate_series(1,{batch_rows});",f'{batch}_insert')
                    inserted+=batch_rows
                    elapsed_reindex='0'
                    if threshold is not None and sql(f"SELECT isam_reorg_needed('bench_idx',{threshold})")=='t':
                        elapsed_reindex=reindex(f'{batch}_reindex')
                    sql('ANALYZE bench')
                    measure(str(batch),elapsed,elapsed_reindex)
                if threshold is None:
                    elapsed=reindex('final_reindex')
                    measure('reindex','0',elapsed)
    metadata.update(status='completed',completed_utc=dt.datetime.now(dt.timezone.utc).isoformat(),csv_sha256=hashlib.sha256(out.read_bytes()).hexdigest())
    out.with_suffix('.json').write_text(json.dumps(metadata,ensure_ascii=False,indent=2))
    print(f'Resultados completos: {out}',flush=True)

if __name__=='__main__': main()
