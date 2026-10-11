#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
docker compose up -d --build
echo "Esperando a PostgreSQL..."
until docker exec isam_pg pg_isready -U postgres -d bd2 >/dev/null 2>&1; do sleep 1; done
docker exec isam_pg psql -U postgres -d bd2 -c "SELECT version();"
docker exec isam_pg psql -U postgres -d bd2 -f /tests/sql/isam_integration.sql
