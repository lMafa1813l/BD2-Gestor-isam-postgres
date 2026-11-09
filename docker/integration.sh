#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "$0")/common.sh"
start_pg
pg_exec psql -X -v ON_ERROR_STOP=1 -U postgres -d bd2 -c "SELECT version();"
integration_output=$(pg_exec psql -X -v ON_ERROR_STOP=1 -U postgres -d bd2 -f /tests/sql/isam_integration.sql)
printf '%s\n' "$integration_output"
if [[ "$integration_output" != *'OK: Bloque 4'* ]]; then
  echo 'La integración terminó sin completar todas sus comprobaciones' >&2
  exit 1
fi
pg_exec psql -X -v ON_ERROR_STOP=1 -U postgres -d bd2 -f /tests/sql/caso-vacuum.sql
