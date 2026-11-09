"""Three-node academic PostgreSQL lab: deterministic shards and snapshot catalogs.

Only the dedicated ``distrib`` database and marked dist/remote_* schemas are reset.
Every node keeps normal B-tree primary keys and foreign keys. ``index`` controls
only the additional orders.customer_id index. Replica refresh is an explicit
snapshot operation, atomic per subscriber; it is not streaming replication or a
distributed transaction. All connections use bounded statement/connect timeouts.
"""
from __future__ import annotations

import hashlib
import os
import time
from typing import Any

import psycopg
from psycopg import sql
from credentials import read_password

NODES = ('a', 'b', 'c')
STRATEGIES = ('regional', 'hash')
INDEXES = ('none', 'btree', 'isam')
LAB_ID = 'bd2_isam_stage_ii'
TABLES = ('customers', 'products', 'orders', 'order_items')


def customer_id(order_id: int) -> int:
    return 1 + (order_id - 1) % 3000


def region_for_order(order_id: int) -> int:
    return (customer_id(order_id) - 1) // 1000


def owner(order_id: int, strategy: str) -> str:
    if order_id < 1 or strategy not in STRATEGIES:
        raise ValueError('Positive order id and regional/hash strategy required')
    return NODES[region_for_order(order_id) if strategy == 'regional' else ((order_id * 1103515245 + 12345) % 2147483647) % 3]


def relation(origin: str, target: str, table: str) -> str:
    if origin not in NODES or target not in NODES or table not in TABLES:
        raise ValueError('Unknown node/table')
    return f'dist.{table}' if origin == target else f'remote_{target}.{table}'


def connect_all() -> dict[str, psycopg.Connection]:
    result = {}
    try:
        for number, node in enumerate(NODES):
            result[node] = psycopg.connect(
                host=os.getenv('DIST_HOST', '127.0.0.1'),
                port=int(os.getenv('DIST_PORT_BASE', '55431')) + number,
                dbname='distrib', user='postgres', password=read_password(),
                autocommit=True, connect_timeout=5, prepare_threshold=None,
                application_name='bd2_distributed_lab',
                options='-c statement_timeout=' + os.getenv('DIST_STATEMENT_TIMEOUT_MS', '120000') +
                        ' -c lock_timeout=10000 -c jit=off -c max_parallel_workers_per_gather=0'
            )
        return result
    except BaseException:
        for connection in result.values():
            connection.close()
        raise


def _one(connection, query: str, params=None):
    return connection.execute(query, params).fetchone()[0]


def _check_owned(connection):
    if connection.info.dbname != 'distrib':
        raise ValueError('Refusing to reset any database except distrib')
    exists = _one(connection, "SELECT EXISTS(SELECT FROM pg_namespace WHERE nspname='dist')")
    marked = _one(connection, "SELECT to_regclass('dist.lab_identity') IS NOT NULL")
    if exists and (not marked or _one(connection, 'SELECT identity FROM dist.lab_identity') != LAB_ID):
        raise ValueError('Existing dist schema is not owned by this lab; preserve it')
    if not exists and _one(connection, "SELECT EXISTS(SELECT FROM pg_namespace WHERE nspname IN ('remote_a','remote_b','remote_c'))"):
        raise ValueError('Existing remote schemas are not owned by this lab; preserve them')
    if int(_one(connection, 'SHOW server_version_num')) != 180006:
        raise ValueError('This experiment requires PostgreSQL 18.6')


def _copy_rows(source, target, table: str, columns: str):
    # Internal table/column constants only; caller does not supply identifiers.
    with source.cursor().copy(f'COPY (SELECT {columns} FROM dist.{table} ORDER BY id) TO STDOUT') as read:
        with target.cursor().copy(f'COPY dist.{table} ({columns}) FROM STDIN') as write:
            for chunk in read:
                write.write(chunk)


def setup(conns: dict, n: int, strategy: str, index: str = 'isam') -> dict[str, Any]:
    """Reset the dedicated lab and independently build N orders and N details.

    Official-size and repetition requirements belong to the experiment runner;
    this primitive also supports explicitly labelled small correctness diagnostics.
    """
    if n < 1 or n > 2_000_000_000 or strategy not in STRATEGIES or index not in INDEXES:
        raise ValueError('Invalid N, strategy or secondary index')
    if set(conns) != set(NODES):
        raise ValueError('Exactly three live node connections are required')
    for connection in conns.values():
        _check_owned(connection)
    started = time.perf_counter()
    stats = {'n': n, 'strategy': strategy, 'index': index, 'nodes': {}}
    for node, connection in conns.items():
        with connection.transaction():
            for other in NODES:
                connection.execute(sql.SQL('DROP SCHEMA IF EXISTS {} CASCADE').format(sql.Identifier('remote_' + other)))
            connection.execute('DROP SCHEMA IF EXISTS dist CASCADE')
            connection.execute('CREATE SCHEMA dist')
            connection.execute('CREATE TABLE dist.lab_identity(identity text PRIMARY KEY)')
            connection.execute('INSERT INTO dist.lab_identity VALUES (%s)', (LAB_ID,))
            connection.execute('CREATE EXTENSION IF NOT EXISTS isam_am')
            connection.execute('CREATE EXTENSION IF NOT EXISTS postgres_fdw')
            connection.execute('''CREATE TABLE dist.customers(
                id integer PRIMARY KEY, region integer NOT NULL CHECK(region BETWEEN 0 AND 2),
                name text NOT NULL)''')
            connection.execute('''CREATE TABLE dist.products(
                id integer PRIMARY KEY, name text NOT NULL,
                price_cents integer NOT NULL CHECK(price_cents > 0))''')
            connection.execute('''CREATE TABLE dist.replica_state(
                singleton boolean PRIMARY KEY DEFAULT true CHECK(singleton),
                version bigint NOT NULL, refreshed_at timestamptz NOT NULL DEFAULT clock_timestamp())''')
            connection.execute('INSERT INTO dist.replica_state(singleton,version) VALUES (true,1)')
            predicate = 'region = ' + str(NODES.index(node)) if strategy == 'regional' else '((id::bigint * 1103515245 + 12345) % 2147483647) % 3 = ' + str(NODES.index(node))
            connection.execute('''CREATE TABLE dist.orders(
                id integer PRIMARY KEY, customer_id integer NOT NULL REFERENCES dist.customers(id),
                region integer NOT NULL CHECK(region BETWEEN 0 AND 2),
                amount_cents integer NOT NULL CHECK(amount_cents > 0),
                status integer NOT NULL DEFAULT 0 CHECK(status >= 0),
                CHECK (region = (customer_id-1)/1000), CHECK (''' + predicate + '''))''')
            connection.execute('''CREATE TABLE dist.order_items(
                order_id integer PRIMARY KEY REFERENCES dist.orders(id),
                product_id integer NOT NULL REFERENCES dist.products(id),
                quantity integer NOT NULL CHECK(quantity BETWEEN 1 AND 5),
                unit_price_cents integer NOT NULL CHECK(unit_price_cents > 0))''')
    # Immutable customers and initially synchronized products are real copies of A.
    conns['a'].execute("INSERT INTO dist.customers SELECT i,(i-1)/1000,'Customer '||i FROM generate_series(1,3000) i")
    conns['a'].execute("INSERT INTO dist.products SELECT i,'Product '||i,100+(i*37)%10000 FROM generate_series(1,1000) i")
    for node in ('b', 'c'):
        with conns[node].transaction():
            _copy_rows(conns['a'], conns[node], 'customers', 'id,region,name')
            _copy_rows(conns['a'], conns[node], 'products', 'id,name,price_cents')
    for node, connection in conns.items():
        number = NODES.index(node)
        predicate = '((i-1)%3000)/1000 = %s' if strategy == 'regional' else '((i::bigint*1103515245+12345)%%2147483647)%%3 = %s'
        # %% is needed only in psycopg query text when parameters are bound.
        predicate = predicate.replace('%3000', '%%3000')
        t0 = time.perf_counter()
        connection.execute('''INSERT INTO dist.orders(id,customer_id,region,amount_cents)
            SELECT i,1+(i-1)%%3000,((i-1)%%3000)/1000,
                   (1+i%%5)*(100+((1+(i-1)%%1000)*37)%%10000)
            FROM generate_series(1,%s) i WHERE ''' + predicate, (n, number))
        connection.execute('''INSERT INTO dist.order_items
            SELECT id,1+(id-1)%1000,1+id%5,100+((1+(id-1)%1000)*37)%10000
            FROM dist.orders''')
        load_ms = (time.perf_counter() - t0)*1000
        connection.execute('SET max_parallel_maintenance_workers=0')
        connection.execute('SET isam_am.fill_pct=80')
        t0 = time.perf_counter()
        if index != 'none':
            connection.execute(sql.SQL('CREATE INDEX orders_customer_idx ON dist.orders USING {}(customer_id)').format(sql.Identifier('isam_am' if index == 'isam' else 'btree')))
        build_ms = (time.perf_counter() - t0)*1000 if index != 'none' else 0.0
        for table in TABLES:
            connection.execute(sql.SQL('VACUUM ANALYZE dist.{}').format(sql.Identifier(table)))
        stats['nodes'][node] = {
            'load_ms': load_ms, 'build_ms': build_ms,
            'orders': _one(connection, 'SELECT count(*) FROM dist.orders'),
            'secondary_index_bytes': _one(connection, "SELECT coalesce(pg_relation_size(to_regclass('dist.orders_customer_idx')),0)"),
            'all_index_bytes': _one(connection, "SELECT pg_indexes_size('dist.orders')"),
        }
    for origin, connection in conns.items():
        for target in NODES:
            if origin == target:
                continue
            server = 'isam_lab_' + target
            connection.execute(sql.SQL('DROP SERVER IF EXISTS {} CASCADE').format(sql.Identifier(server)))
            connection.execute(sql.SQL("CREATE SERVER {} FOREIGN DATA WRAPPER postgres_fdw OPTIONS (host {}, port '5432', dbname 'distrib', fetch_size '1000', connect_timeout '3')").format(sql.Identifier(server), sql.Literal('pg-' + target)))
            connection.execute(sql.SQL("CREATE USER MAPPING FOR CURRENT_USER SERVER {} OPTIONS (user 'postgres', password {})").format(sql.Identifier(server), sql.Literal(read_password())))
            connection.execute(sql.SQL('CREATE SCHEMA {}').format(sql.Identifier('remote_' + target)))
            connection.execute(sql.SQL('IMPORT FOREIGN SCHEMA dist LIMIT TO (customers,products,orders,order_items) FROM SERVER {} INTO {}').format(sql.Identifier(server), sql.Identifier('remote_' + target)))
        for table in ('orders', 'order_items'):
            union = ' UNION ALL '.join('SELECT * FROM '+relation(origin, target, table) for target in NODES)
            connection.execute('CREATE VIEW dist.all_' + table + ' AS ' + union)
    stats['setup_ms'] = (time.perf_counter()-started)*1000
    return stats


def _reference(n: int) -> dict:
    # Independent Python oracle; the deterministic pattern repeats every 3000 ids.
    cycle = 3000
    sums = {'customer': 0, 'amount': 0, 'quantity': 0, 'product': 0}
    for i in range(1, cycle+1):
        repetitions = n//cycle + int(i <= n%cycle)
        product = 1 + (i-1)%1000
        quantity = 1+i%5
        sums['customer'] += repetitions*customer_id(i)
        sums['amount'] += repetitions*quantity*(100+(product*37)%10000)
        sums['quantity'] += repetitions*quantity
        sums['product'] += repetitions*product
    return {'count': n, 'sum_ids': n*(n+1)//2, **{'sum_'+k: v for k,v in sums.items()}}


def validate(conns: dict, n: int, strategy: str, expected_status_sum: int = 0, full_fdw_fingerprint: bool = True) -> dict:
    """Check all shards, FK joins, allocation and FDW against a Python oracle.

    status is the only benchmark-mutated field; pass the expected count of status
    increments after a workload. Fingerprints deliberately cover immutable order
    data; the separate status aggregate tests the committed writes.
    """
    expected = _reference(n)
    totals = dict(count=0, sum_ids=0, sum_customer=0, sum_amount=0,
                  sum_quantity=0, sum_product=0, sum_status=0)
    result = {'nodes': {}, 'fdw_checks': []}
    digests = []
    for node, connection in conns.items():
        row = connection.execute('''SELECT count(*),coalesce(sum(o.id),0),
            coalesce(sum(o.customer_id),0),coalesce(sum(o.amount_cents),0),
            coalesce(sum(i.quantity),0),coalesce(sum(i.product_id),0),coalesce(sum(o.status),0),
            count(*) FILTER(WHERE o.region <> c.region OR o.amount_cents <> i.quantity*i.unit_price_cents)
            FROM dist.orders o JOIN dist.order_items i ON i.order_id=o.id
            JOIN dist.customers c ON c.id=o.customer_id JOIN dist.products p ON p.id=i.product_id''').fetchone()
        counts = dict(zip(totals, map(int,row[:7])))
        if row[7] or counts['count'] != _one(connection, 'SELECT count(*) FROM dist.orders') or counts['count'] != _one(connection, 'SELECT count(*) FROM dist.order_items'):
            raise AssertionError(f'Broken relationships or missing details on {node}')
        wrong = _one(connection, 'SELECT count(*) FROM dist.orders WHERE '+ ('region' if strategy=='regional' else '((id::bigint*1103515245+12345)%2147483647)%3') + ' <> '+str(NODES.index(node)))
        if wrong:
            raise AssertionError(f'Wrong fragment ownership on {node}')
        digest = _one(connection, "SELECT md5(coalesce(string_agg(id::text||':'||customer_id||':'||region||':'||amount_cents,',' ORDER BY id),'')) FROM dist.orders")
        result['nodes'][node] = {**counts, 'fingerprint': digest}
        for key in totals:
            totals[key] += counts[key]
        digests.append(digest)
    for key, value in expected.items():
        if totals[key] != value:
            raise AssertionError(f'Oracle mismatch {key}: {totals[key]} != {value}')
    if totals['sum_status'] != expected_status_sum:
        raise AssertionError(f"Committed status increments {totals['sum_status']} != {expected_status_sum}")
    # Every origin genuinely traverses postgres_fdw to the other two nodes.
    global_fingerprints = []
    for origin, connection in conns.items():
        if origin != 'a' and not full_fdw_fingerprint:
            branches = [f'SELECT count(*) n, sum(id) ids, sum(amount_cents) amt, sum(status) st FROM {relation(origin,target,"orders")}' for target in NODES]
            row = connection.execute('SELECT sum(n),sum(ids),sum(amt),sum(st) FROM ('+' UNION ALL '.join(branches)+') q').fetchone()
            if tuple(map(int,row)) != (n,expected['sum_ids'],expected['sum_amount'],expected_status_sum):
                raise AssertionError(f'FDW aggregate mismatch at {origin}')
            result['fdw_checks'].append({'origin':origin,'count':int(row[0]),'sum_ids':int(row[1]),'sum_amount_cents':int(row[2]),'sum_status':int(row[3]),'check':'remote aggregates'})
            continue
        row = connection.execute('''SELECT count(*),sum(id),sum(amount_cents),sum(status),
            md5(string_agg(id::text||':'||customer_id||':'||region||':'||amount_cents,',' ORDER BY id)),
            count(DISTINCT id), min(id), max(id)
            FROM dist.all_orders''').fetchone()
        if tuple(map(int,row[:4])) != (n,expected['sum_ids'],expected['sum_amount'],expected_status_sum):
            raise AssertionError(f'FDW result differs from independent reference at {origin}')
        if tuple(map(int,row[5:])) != (n,1,n):
            raise AssertionError('Global ids are duplicated, missing or out of domain')
        global_fingerprints.append(row[4])
        result['fdw_checks'].append({'origin':origin,'count':int(row[0]),'sum_ids':int(row[1]),'sum_amount_cents':int(row[2]),'sum_status':int(row[3]),'fingerprint':row[4]})
    if len(set(global_fingerprints)) != 1:
        raise AssertionError('Global order fingerprints differ between origins')
    catalogs = []
    for connection in conns.values():
        catalogs.append(_one(connection, "SELECT md5(string_agg(id::text||':'||name||':'||price_cents,',' ORDER BY id)) FROM dist.products"))
    if len(set(catalogs)) != 1:
        raise AssertionError('Product replicas are not synchronized')
    result.update(totals)
    result.update(sum_amount_cents=totals['sum_amount'], fingerprint=global_fingerprints[0],
                  n=n, strategy=strategy, status='passed', catalog_fingerprint=catalogs[0])
    return result


def refresh_products(conns: dict) -> dict:
    """Publish A's current products as a consistent snapshot on B and C.

    A increments its version and reads all product rows in one REPEATABLE READ
    transaction. Each subscriber upserts that snapshot and its version in one
    local transaction. No cross-node atomicity, deletion or automatic failover is
    claimed. Callers must use A as the sole catalog writer and serialize refresh.
    """
    source = conns['a']
    with source.transaction():
        source.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ')
        version = _one(source, 'UPDATE dist.replica_state SET version=version+1, refreshed_at=clock_timestamp() RETURNING version')
        rows = source.execute('SELECT id,name,price_cents FROM dist.products ORDER BY id').fetchall()
    result = {'version': int(version), 'rows': len(rows), 'subscribers': {}}
    for node in ('b','c'):
        started = time.perf_counter()
        with conns[node].transaction():
            conns[node].execute('CREATE TEMP TABLE catalog_snapshot(LIKE dist.products INCLUDING ALL) ON COMMIT DROP')
            with conns[node].cursor().copy('COPY catalog_snapshot (id,name,price_cents) FROM STDIN') as write:
                for row in rows:
                    write.write_row(row)
            conns[node].execute('''INSERT INTO dist.products SELECT * FROM catalog_snapshot
                ON CONFLICT(id) DO UPDATE SET name=excluded.name, price_cents=excluded.price_cents''')
            conns[node].execute('UPDATE dist.replica_state SET version=%s,refreshed_at=clock_timestamp()', (version,))
        result['subscribers'][node] = {'version': int(version), 'refresh_ms': (time.perf_counter()-started)*1000}
    return result
