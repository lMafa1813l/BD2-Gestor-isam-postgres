#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
docker compose up -d --build
wait_pg() { until docker exec isam_pg pg_isready -U postgres -d bd2 >/dev/null 2>&1; do sleep 1; done; }
wait_pg
docker exec isam_pg psql -U postgres -d bd2 -f /tests/sql/crash_1.sql
docker kill isam_pg
docker start isam_pg
sleep 3
wait_pg
docker exec isam_pg psql -U postgres -d bd2 -f /tests/sql/crash_2.sql
