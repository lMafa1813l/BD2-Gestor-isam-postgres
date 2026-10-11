#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
docker compose up -d --build
echo "Esperando a PostgreSQL..."
until docker exec isam_pg pg_isready -U postgres -d bd2 >/dev/null 2>&1; do sleep 1; done
docker exec isam_pg psql -U postgres -d bd2 -qc "CREATE EXTENSION IF NOT EXISTS isam_am; ALTER EXTENSION isam_am UPDATE;"
export PSQL="docker exec -i isam_pg psql -X -q -At -U postgres -d bd2"
export PGBENCH="docker exec -i isam_pg pgbench -U postgres"
export PGB_DB=bd2
export WORKLOADS=/workloads
../benchmarks/run_bench.sh
