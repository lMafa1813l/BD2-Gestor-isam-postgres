#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
docker compose up -d --build
wait_pg() { until docker exec isam_pg pg_isready -U postgres -d bd2 >/dev/null 2>&1; do sleep 1; done; }
wait_pg
docker exec isam_pg psql -U postgres -d bd2 -f /tests/sql/crash_load_1.sql
docker exec -d isam_pg pgbench -U postgres -n -c 6 -j 3 -T 30 -D dom=20000 -f /workloads/w3_insert.pgb bd2
sleep 5
docker kill isam_pg
docker start isam_pg
sleep 3
wait_pg
docker exec isam_pg psql -U postgres -d bd2 -f /tests/sql/crash_load_2.sql
