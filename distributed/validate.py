"""Executable acceptance checks: allocation, joins, replica lag and node outage."""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
from pathlib import Path
import subprocess
import time

import psycopg

import db
from experiment import dump, file_hash


def prices(conns):
    return {node: list(conn.execute('SELECT price_cents,(SELECT version FROM dist.replica_state) FROM dist.products WHERE id=1').fetchone()) for node,conn in conns.items()}


def docker_node(action, node):
    project = os.getenv('DIST_PROJECT', 'bd2_dist')
    name = project+'_'+node
    label = subprocess.check_output(['docker','inspect',name,'--format','{{index .Config.Labels "com.docker.compose.project"}}'], text=True).strip()
    if label != project:
        raise ValueError('Refusing to stop a container outside this lab')
    subprocess.run(['docker',action,name], check=True, capture_output=True, text=True)


def recover_c(conns):
    docker_node('start','c')
    deadline = time.monotonic()+60
    last = None
    while time.monotonic() < deadline:
        try:
            new = db.connect_all()
            for conn in conns.values(): conn.close()
            conns.clear();conns.update(new)
            return
        except psycopg.Error as exc:
            last=exc
            time.sleep(0.5)
    raise RuntimeError('C did not recover within 60 seconds') from last


def scenario(conns, n, strategy):
    setup = db.setup(conns,n,strategy,'isam')
    initial = db.validate(conns,n,strategy)
    # Genuine cross-node join: remote order/detail plus local replicated catalogs.
    join = conns['a'].execute('''SELECT count(*),sum(i.quantity*i.unit_price_cents)
        FROM remote_c.orders o JOIN remote_c.order_items i ON i.order_id=o.id
        JOIN dist.customers c ON c.id=o.customer_id
        JOIN dist.products p ON p.id=i.product_id''').fetchone()
    expected = conns['c'].execute('SELECT count(*),sum(amount_cents) FROM dist.orders').fetchone()
    if join != expected:
        raise AssertionError('Cross-node four-table join differs from local reference')
    before = prices(conns)
    conns['a'].execute('UPDATE dist.products SET price_cents=price_cents+17 WHERE id=1')
    stale = prices(conns)
    if stale['a'][0] != before['a'][0]+17 or stale['b'] != before['b'] or stale['c'] != before['c']:
        raise AssertionError('Replica lag was not visible before explicit refresh')
    refresh = db.refresh_products(conns)
    synced = prices(conns)
    if len({tuple(v) for v in synced.values()}) != 1 or synced['a'][1] != before['a'][1]+1:
        raise AssertionError('Replica snapshot/version did not converge')
    db.validate(conns,n,strategy)
    local_id = conns['a'].execute('SELECT min(id) FROM dist.orders').fetchone()[0]
    remote_id = conns['c'].execute('SELECT min(id) FROM dist.orders').fetchone()[0]
    outage = {'target':'c','expected_failures':[]}
    conns['c'].close()
    down = False
    try:
        docker_node('stop','c');down=True
        for node in ('a','b'):
            if conns[node].execute('SELECT count(*) FROM dist.products').fetchone()[0] != 1000:
                raise AssertionError('Local replicated catalog disappeared')
            if conns[node].execute('SELECT count(*) FROM dist.orders').fetchone()[0] <= 0:
                raise AssertionError('Healthy local fragment unavailable')
        # A write that only needs A remains available and commits exactly once.
        updated = conns['a'].execute('UPDATE dist.orders SET status=status+1 WHERE id=%s RETURNING status',(local_id,)).fetchone()[0]
        if updated != 1:
            raise AssertionError('Healthy-node write did not commit')
        for label,query,params in [
            ('global_read','SELECT count(*) FROM dist.all_orders',()),
            ('remote_write','UPDATE remote_c.orders SET status=status+1 WHERE id=%s RETURNING status',(remote_id,))]:
            try:
                conns['a'].execute(query,params).fetchall()
            except psycopg.Error as exc:
                outage['expected_failures'].append(dict(operation=label,sqlstate=exc.sqlstate,error=str(exc)))
            else:
                raise AssertionError(f'{label} silently succeeded with C down')
        outage.update(local_reads='passed',local_write_status=updated,
                      catalog_reads='passed',partial_global_result=False)
    finally:
        if down:
            recover_c(conns)
    recovered = db.validate(conns,n,strategy,expected_status_sum=1)
    outage['recovery']='passed'
    return dict(status='passed',n=n,strategy=strategy,setup=setup,
                initial=initial,cross_node_join=list(join),
                replicas=dict(before=before,stale=stale,refresh=refresh,synced=synced),
                outage=outage,recovered=recovered)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--n',type=int,default=6000)
    parser.add_argument('--reps',type=int,default=1)
    parser.add_argument('--official',action='store_true')
    parser.add_argument('--out',type=Path)
    args=parser.parse_args()
    if args.n<3000 or args.reps<1:
        parser.error('N>=3000 and reps>=1 required')
    if args.official and (args.n<1000000 or args.reps<5):
        parser.error('Official checks require N>=1M and at least 5 repetitions')
    stamp=dt.datetime.now(dt.timezone.utc).strftime('%Y%m%d_%H%M%S')
    out=args.out or Path(__file__).resolve().parent/'results'/('validation_'+stamp)
    out.mkdir(parents=True,exist_ok=False)
    meta=dict(status='running',n=args.n,reps=args.reps,smoke=not args.official,
              started_utc=dt.datetime.now(dt.timezone.utc).isoformat(),scenarios=[])
    dump(out/'metadata.json',meta)
    conns={}
    try:
        conns=db.connect_all()
        for rep in range(1,args.reps+1):
            for strategy in db.STRATEGIES:
                print(f'>> validation r{rep} {strategy} N={args.n}',flush=True)
                result=scenario(conns,args.n,strategy)
                name=f'r{rep}_{strategy}.json'
                dump(out/name,result)
                meta['scenarios'].append(dict(file=name,sha256=file_hash(out/name),status='passed'))
                dump(out/'metadata.json',meta)
        meta.update(status='completed',completed_utc=dt.datetime.now(dt.timezone.utc).isoformat())
        dump(out/'metadata.json',meta)
        print('All acceptance checks passed: '+str(out),flush=True)
    except BaseException as exc:
        meta.update(status='failed',error=repr(exc));dump(out/'metadata.json',meta)
        raise
    finally:
        for conn in conns.values():conn.close()


if __name__=='__main__':main()
