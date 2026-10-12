#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "$0")/common.sh"
start_pg
pg_exec psql -X -v ON_ERROR_STOP=1 -U postgres -d bd2 -c "SELECT version();"
pg_exec psql -X -v ON_ERROR_STOP=1 -U postgres -d bd2 -f /tests/sql/isam_integration.sql
pg_exec psql -X -v ON_ERROR_STOP=1 -U postgres -d bd2 -f /tests/sql/caso-vacuum.sql
