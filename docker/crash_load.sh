#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "$0")/common.sh"
start_pg
pg_exec psql -X -v ON_ERROR_STOP=1 -U postgres -d bd2 -f /tests/sql/crash_load_1.sql
docker exec -d "$ISAM_CONTAINER_NAME" pgbench -U postgres -n -c 6 -j 3 -T 30 --random-seed=42000 -D dom=20000 -f /workloads/w3_insert.pgb bd2
sleep 5
docker kill "$ISAM_CONTAINER_NAME"
docker start "$ISAM_CONTAINER_NAME"
wait_pg
pg_exec psql -X -v ON_ERROR_STOP=1 -U postgres -d bd2 -f /tests/sql/crash_load_2.sql
