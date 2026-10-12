#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "$0")/common.sh"
start_pg
pg_exec psql -X -v ON_ERROR_STOP=1 -U postgres -d bd2 -f /tests/sql/crash_1.sql
docker kill "$ISAM_CONTAINER_NAME"
docker start "$ISAM_CONTAINER_NAME"
wait_pg
pg_exec psql -X -v ON_ERROR_STOP=1 -U postgres -d bd2 -f /tests/sql/crash_2.sql
