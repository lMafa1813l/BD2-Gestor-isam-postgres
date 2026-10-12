#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "$0")/common.sh"
start_pg
if ! pg_exec psql -X -At -U postgres -d postgres -c "SELECT 1 FROM pg_database WHERE datname='isam_overflow'" | awk '$0==1 {found=1} END {exit !found}'; then
  pg_exec createdb -U postgres isam_overflow
fi
pg_exec psql -X -v ON_ERROR_STOP=1 -U postgres -d isam_overflow -c "CREATE EXTENSION IF NOT EXISTS isam_am; ALTER EXTENSION isam_am UPDATE;"
export PSQL="docker exec -i $ISAM_CONTAINER_NAME psql -X -q -At -U postgres -d isam_overflow"
export PGBENCH="docker exec -i $ISAM_CONTAINER_NAME pgbench -U postgres"
export PGB_DB=isam_overflow
export WORKLOADS=/workloads
export DATASETS_DIR=/datasets
bash "$repo_dir/benchmarks/run_overflow.sh"
