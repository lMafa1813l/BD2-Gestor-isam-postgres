"""Reproducible real FDW workloads with an explicitly simulated link cost."""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import platform
import random
import statistics
import subprocess
import time

import db

ROOT = Path(__file__).resolve().parents[1]
LINK_MS = {frozenset(('a', 'b')): 20, frozenset(('a', 'c')): 40,
           frozenset(('b', 'c')): 25}


def dump(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, default=str)+'\n')


def file_hash(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def counters():
    result = {}
    project = os.getenv('DIST_PROJECT', 'bd2_dist')
    for node in db.NODES:
        values = subprocess.check_output(['docker', 'exec', project+'_'+node,
            'cat', '/sys/class/net/eth0/statistics/rx_bytes',
            '/sys/class/net/eth0/statistics/tx_bytes'], text=True).split()
        result[node] = dict(zip(('rx_bytes', 'tx_bytes'), map(int, values)))
    return result


def operations(n, count, seed, profile):
    """Exactly 50% customer reads, 20% range reads and 30% committed updates."""
    rng = random.Random(seed)
    kinds = ['customer']*(count//2) + ['range']*(count//5) + ['write']*(3*count//10)
    rng.shuffle(kinds)
    result = []
    for number, kind in enumerate(kinds):
        weights = [1, 1, 1] if profile == 'balanced' else [1, 1, 8]
        origin = rng.choices(db.NODES, weights=weights)[0]
        customer = db.NODES.index(origin)*1000 + rng.randint(1, 1000)
        # Pick a real order from that customer's region for a local-site request.
        candidates = (n-customer)//3000+1
        if candidates <= 0:
            raise ValueError('N>=3000 is required to represent every customer')
        order_id = customer + 3000*rng.randrange(candidates)
        lo = rng.randint(1, max(1, n-99))
        result.append(dict(number=number, kind=kind, origin=origin, customer=customer,
                           order_id=order_id, lo=lo, hi=min(n, lo+99)))
    return result


def query_for(op, strategy):
    origin, kind = op['origin'], op['kind']
    if kind == 'write':
        target = db.owner(op['order_id'], strategy)
        table = db.relation(origin, target, 'orders')
        return f'UPDATE {table} SET status=status+1 WHERE id=%s::int4 RETURNING id,status', (op['order_id'],), [target]
    if kind == 'customer':
        targets = [db.NODES[(op['customer']-1)//1000]] if strategy == 'regional' else list(db.NODES)
        branches = [f'SELECT count(amount_cents) AS n,coalesce(sum(status),0) AS s FROM {db.relation(origin,t,"orders")} WHERE customer_id=%s::int4' for t in targets]
        return 'SELECT sum(n)::bigint,sum(s)::bigint FROM ('+' UNION ALL '.join(branches)+') q', tuple([op['customer']]*len(targets)), targets
    branches = [f'SELECT count(amount_cents) AS n,coalesce(sum(status),0) AS s FROM {db.relation(origin,t,"orders")} WHERE id BETWEEN %s::int4 AND %s::int4' for t in db.NODES]
    return 'SELECT sum(n)::bigint,sum(s)::bigint FROM ('+' UNION ALL '.join(branches)+') q', tuple([op['lo'], op['hi']]*3), list(db.NODES)


def expected_result(op, n, statuses):
    if op['kind'] == 'write':
        key = op['order_id']
        return key, statuses.get(key, 0)+1
    if op['kind'] == 'customer':
        key = op['customer']
        count = (n-key)//3000+1
        return count, sum(v for k,v in statuses.items() if db.customer_id(k) == key)
    return op['hi']-op['lo']+1, sum(v for k,v in statuses.items() if op['lo'] <= k <= op['hi'])


def save_plans(conns, directory, config):
    plans = {}
    for node, conn in conns.items():
        customer = conn.execute('SELECT customer_id FROM dist.orders ORDER BY id LIMIT 1').fetchone()[0]
        query = 'EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) SELECT count(amount_cents) FROM dist.orders WHERE customer_id=%s::int4'
        plans[node] = {'normal': conn.execute(query, (customer,)).fetchone()[0]}
        if config != 'none':
            conn.execute('SET enable_seqscan=off')
            try:
                plans[node]['diagnostic_forced'] = conn.execute(query, (customer,)).fetchone()[0]
            finally:
                conn.execute('RESET enable_seqscan')
            if 'orders_customer_idx' not in json.dumps(plans[node]['diagnostic_forced']):
                raise AssertionError(f'Secondary {config} index was not exercised on {node}')
    plans['fdw'] = conns['a'].execute('EXPLAIN (ANALYZE, VERBOSE, FORMAT JSON) SELECT count(amount_cents) FROM remote_b.orders WHERE customer_id=1001').fetchone()[0]
    if 'Foreign Scan' not in json.dumps(plans['fdw']):
        raise AssertionError('No genuine Foreign Scan found')
    dump(directory/'plans.json', plans)


def run_trial(conns, args, rep, strategy, config, profile, mode, directory):
    directory.mkdir()
    setup = db.setup(conns, args.n, strategy, config)
    before = db.validate(conns, args.n, strategy, full_fdw_fingerprint=False)
    save_plans(conns, directory, config)
    ops = operations(args.n, args.ops, args.seed+rep, profile)
    digest = hashlib.sha256(json.dumps(ops, sort_keys=True).encode()).hexdigest()
    statuses, rows = {}, []
    transfer_before = counters()
    for op in ops:
        query, params, targets = query_for(op, strategy)
        remote = sorted(set(targets)-{op['origin']})
        delay = sum(LINK_MS[frozenset((op['origin'], t))] for t in remote) if mode == 'model' else 0
        started = time.perf_counter()
        if delay:
            time.sleep(delay/1000)
        db_started = time.perf_counter()
        observed = tuple(map(int, conns[op['origin']].execute(query, params).fetchone()))
        db_ms = (time.perf_counter()-db_started)*1000
        elapsed_ms = (time.perf_counter()-started)*1000
        expected = expected_result(op, args.n, statuses)
        if observed != expected:
            raise AssertionError(f'Workload oracle mismatch: {op}: {observed} != {expected}')
        if op['kind'] == 'write':
            statuses[op['order_id']] = observed[1]
        rows.append({**op, 'remote_targets': ','.join(remote), 'model_ms': delay,
                     'db_ms': db_ms, 'elapsed_ms': elapsed_ms,
                     'logical_result_bytes': len(json.dumps(observed).encode()),
                     'result': observed})
    transfer_after = counters()
    after = db.validate(conns, args.n, strategy, 3*args.ops//10, full_fdw_fingerprint=False)
    if after['fingerprint'] != before['fingerprint']:
        raise AssertionError('Immutable order content changed')
    if sum(op['kind'] == 'write' for op in rows) != 3*args.ops//10:
        raise AssertionError('Workload is not 70/30')
    transfer = {node: {key: transfer_after[node][key]-transfer_before[node][key]
                      for key in ('rx_bytes', 'tx_bytes')} for node in db.NODES}
    dump(directory/'trial.json', dict(setup=setup, before=before, after=after,
         input_sha256=digest, transfer=transfer, operations=rows))
    fields = dict(rep=rep, n=args.n, strategy=strategy, config=config, profile=profile,
                  latency_mode=mode, operations=args.ops, reads=7*args.ops//10,
                  writes=3*args.ops//10, failures=0, seed=args.seed+rep,
                  input_sha256=digest, fingerprint=before['fingerprint'],
                  sum_status=after['sum_status'], setup_ms=setup['setup_ms'],
                  build_ms=sum(v['build_ms'] for v in setup['nodes'].values()),
                  secondary_index_bytes=sum(v['secondary_index_bytes'] for v in setup['nodes'].values()),
                  rx_bytes=sum(v['rx_bytes'] for v in transfer.values()),
                  tx_bytes=sum(v['tx_bytes'] for v in transfer.values()),
                  logical_result_bytes=sum(op['logical_result_bytes'] for op in rows),
                  mean_db_ms=statistics.mean(op['db_ms'] for op in rows),
                  mean_elapsed_ms=statistics.mean(op['elapsed_ms'] for op in rows),
                  mean_model_ms=statistics.mean(op['model_ms'] for op in rows),
                  remote_operations=sum(bool(op['remote_targets']) for op in rows),
                  origin_c_operations=sum(op['origin']=='c' for op in rows))
    for kind in ('customer', 'range', 'write'):
        subset = [op for op in rows if op['kind'] == kind]
        for key in ('db_ms', 'elapsed_ms', 'model_ms'):
            fields[kind+'_'+key] = statistics.mean(op[key] for op in subset)
    return fields


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--n', type=int, default=1000000)
    parser.add_argument('--reps', type=int, default=5)
    parser.add_argument('--ops', type=int, default=100)
    parser.add_argument('--seed', type=int, default=42000)
    parser.add_argument('--configs', nargs='+', choices=db.INDEXES, default=list(db.INDEXES))
    parser.add_argument('--strategies', nargs='+', choices=db.STRATEGIES, default=list(db.STRATEGIES))
    parser.add_argument('--profiles', nargs='+', choices=('balanced','hot_c'), default=['balanced','hot_c'])
    parser.add_argument('--latency-modes', nargs='+', choices=('base','model'), default=['model'])
    parser.add_argument('--smoke', action='store_true')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    if args.n < 3000 or args.ops < 10 or args.ops % 10 or args.reps < 1:
        parser.error('N>=3000, ops>=10 divisible by ten, reps>=1')
    if not args.smoke and (args.n < 1000000 or args.reps < 5 or args.ops < 100):
        parser.error('Official experiments require N>=1M, reps>=5, ops>=100; use --smoke for diagnostics')
    stamp = dt.datetime.now(dt.timezone.utc).strftime('%Y%m%d_%H%M%S')
    out = args.out or ROOT/'distributed/results'/stamp
    out.mkdir(parents=True, exist_ok=False)
    csv_path = out/'trials.csv'
    metadata = dict(status='running', started_utc=dt.datetime.now(dt.timezone.utc).isoformat(),
        **{k:v for k,v in vars(args).items() if k!='out'},
        link_model_ms={'A-B':20, 'A-C':40, 'B-C':25},
        link_model='Simulated additive RTT per remote destination before actual SQL, no network shaping',
        transfer_method='eth0 RX/TX deltas per node, protocol/client/FDW included; opposite endpoints double count',
        input_hashes={str(p.relative_to(ROOT)):file_hash(p) for p in (ROOT/'distributed').glob('*') if p.suffix in ('.py','.yml','.sh')},
        python_version=platform.python_version(),
        docker_images={node:subprocess.check_output(['docker','inspect',os.getenv('DIST_PROJECT','bd2_dist')+'_'+node,'--format','{{.Image}}'],text=True).strip() for node in db.NODES},
        isam_source_sha256={str(p.relative_to(ROOT)):file_hash(p) for p in (ROOT/'isam_am').rglob('*') if p.suffix in ('.c','.h','.sql')},
        git_base=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        platform=platform.platform(), host_cpus=os.cpu_count(),
        host_memory=Path('/proc/meminfo').read_text().splitlines()[0],
        cgroup={name:Path('/sys/fs/cgroup/'+name).read_text().strip() for name in ('cpu.max','memory.max') if Path('/sys/fs/cgroup/'+name).exists()})
    dump(out/'metadata.json', metadata)
    conns = {}
    try:
        conns = db.connect_all()
        metadata['nodes'] = {node: {'version':conn.execute('SELECT version()').fetchone()[0],
            'settings':dict(conn.execute("SELECT name,setting FROM pg_settings WHERE name IN ('fsync','synchronous_commit','full_page_writes','shared_buffers','jit','max_parallel_workers_per_gather','max_parallel_maintenance_workers')").fetchall())} for node,conn in conns.items()}
        with csv_path.open('x', newline='') as fh:
            writer, digests, fingerprints = None, {}, set()
            for rep in range(1,args.reps+1):
                for strategy in args.strategies:
                    for config in args.configs:
                        for profile in args.profiles:
                            for mode in args.latency_modes:
                                label=f'r{rep}_{strategy}_{config}_{profile}_{mode}'
                                print('>> '+label,flush=True)
                                row = run_trial(conns,args,rep,strategy,config,profile,mode,out/label)
                                key=(rep,profile)
                                if digests.setdefault(key,row['input_sha256']) != row['input_sha256']:
                                    raise AssertionError('Alternatives used different logical operations')
                                fingerprints.add(row['fingerprint'])
                                if len(fingerprints) != 1:
                                    raise AssertionError('Alternatives used different initial content')
                                if writer is None:
                                    writer=csv.DictWriter(fh,fieldnames=list(row));writer.writeheader()
                                writer.writerow(row);fh.flush()
                                print(f"   {args.ops} ops correct; mean elapsed={row['mean_elapsed_ms']:.3f} ms",flush=True)
        metadata['artifacts_sha256']={str(p.relative_to(out)):file_hash(p) for p in out.glob('r*/*.json')}
        metadata.update(status='completed', csv_sha256=file_hash(csv_path),
                        completed_utc=dt.datetime.now(dt.timezone.utc).isoformat(),
                        observations=args.reps*len(args.strategies)*len(args.configs)*len(args.profiles)*len(args.latency_modes))
        dump(out/'metadata.json',metadata)
        print('Completed: '+str(out),flush=True)
    except BaseException as exc:
        metadata.update(status='failed', failure=repr(exc))
        dump(out/'metadata.json',metadata)
        raise
    finally:
        for conn in conns.values(): conn.close()


if __name__ == '__main__':
    main()
