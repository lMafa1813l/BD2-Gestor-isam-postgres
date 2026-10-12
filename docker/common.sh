#!/usr/bin/env bash
set -euo pipefail
docker_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
repo_dir=$(dirname "$docker_dir")
export ISAM_CONTAINER_NAME="${ISAM_CONTAINER_NAME:-isam_pg}"
mkdir -p "$repo_dir/.cache"
exec 9>"$repo_dir/.cache/$ISAM_CONTAINER_NAME.lock"
flock -n 9 || { echo "Otro flujo está usando $ISAM_CONTAINER_NAME; esperar antes de medir o reiniciar." >&2; exit 1; }
if [ ! -w "$HOME" ] && [ -z "${DOCKER_CONFIG:-}" ]; then
  export DOCKER_CONFIG="$repo_dir/.cache/docker"
  mkdir -p "$DOCKER_CONFIG"
fi
if [ -n "${HTTPS_PROXY:-}" ]; then
  export BUILD_PROXY_HOST
  BUILD_PROXY_HOST=$(python3 -c 'import os,urllib.parse; print(urllib.parse.urlsplit(os.environ["HTTPS_PROXY"]).hostname)')
  export BUILD_PROXY_IP
  BUILD_PROXY_IP=$(getent ahostsv4 "$BUILD_PROXY_HOST" | awk 'NR==1 {address=$1} END {print address}')
  test -n "$BUILD_PROXY_IP"
fi
compose() { docker compose -f "$docker_dir/docker-compose.yml" "$@"; }
pg_exec() { docker exec "$ISAM_CONTAINER_NAME" "$@"; }
wait_pg() {
  for ((attempt=0; attempt<60; attempt++)); do
    if pg_exec pg_isready -U postgres -d bd2 >/dev/null 2>&1; then
      version=$(pg_exec psql -X -At -U postgres -d bd2 -c 'SHOW server_version_num')
      test "$version" = 180006 || { echo "Se requiere PostgreSQL 18.6, encontrado $version" >&2; return 1; }
      return 0
    fi
    sleep 1
  done
  compose logs --tail=80 pg >&2
  echo 'PostgreSQL no estuvo disponible dentro de 60 segundos' >&2
  return 1
}
start_pg() { compose up -d --build; wait_pg; }
