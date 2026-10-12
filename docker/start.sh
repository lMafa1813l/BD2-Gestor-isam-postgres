#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "$0")/common.sh"
start_pg
pg_exec psql -X -v ON_ERROR_STOP=1 -U postgres -d bd2 \
  -c 'SELECT version(); CREATE EXTENSION IF NOT EXISTS isam_am;'
