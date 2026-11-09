#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
export DIST_PROJECT="${DIST_PROJECT:-bd2_dist}"
export DIST_PORT_BASE="${DIST_PORT_BASE:-55431}"
export DIST_PORT_A="$DIST_PORT_BASE" DIST_PORT_B="$((DIST_PORT_BASE+1))" DIST_PORT_C="$((DIST_PORT_BASE+2))"
export DIST_PASSWORD_FILE
DIST_PASSWORD_FILE=$(python3 distributed/credentials.py --create)
mkdir -p .cache
exec 9>".cache/$DIST_PROJECT.lock"
flock -n 9 || { echo "Otro flujo utiliza $DIST_PROJECT" >&2; exit 1; }
if [ ! -w "$HOME" ] && [ -z "${DOCKER_CONFIG:-}" ]; then
  export DOCKER_CONFIG="$PWD/.cache/docker"
  mkdir -p "$DOCKER_CONFIG"
fi
compose() { docker compose -f distributed/compose.yml "$@"; }
build() {
  local build_options=()
  if [ -n "${HTTPS_PROXY:-}" ]; then
    local proxy_host proxy_ip
    proxy_host=$(python3 -c 'import os,urllib.parse; print(urllib.parse.urlsplit(os.environ["HTTPS_PROXY"]).hostname)')
    proxy_ip=$(getent ahostsv4 "$proxy_host" | awk 'NR==1 {a=$1} END {print a}')
    test -n "$proxy_ip"
    build_options+=(--add-host "$proxy_host:$proxy_ip")
  fi
  for recipe in docker/Dockerfile distributed/Dockerfile; do
    local tag=bd2-isam-base:18.6
    [ "$recipe" = docker/Dockerfile ] || tag=bd2-isam-distributed:18.6
    docker build --network host "${build_options[@]}" \
      --build-arg HTTP_PROXY --build-arg HTTPS_PROXY --build-arg http_proxy --build-arg https_proxy \
      --secret "id=proxy_ca,src=${CODEX_PROXY_CERT:-/etc/ssl/certs/ca-certificates.crt}" \
      -t "$tag" -f "$recipe" .
  done
}
start() {
  if ! docker image inspect bd2-isam-distributed:18.6 >/dev/null 2>&1; then build; fi
  compose up -d --wait --wait-timeout 90
  for node in a b c; do
    test "$(docker exec "${DIST_PROJECT}_$node" psql -X -At -U postgres -d distrib -c 'SHOW server_version_num')" = 180006
  done
}
python_run() { "${DIST_PYTHON:-.venv-dist/bin/python}" "$@"; }
action="${1:-up}"
shift || true
case "$action" in
  build) build ;;
  up) start ;;
  stop) compose stop ;;
  status) compose ps ;;
  smoke) start; python_run distributed/experiment.py --smoke --n 6000 --reps 1 --ops 10 --configs isam --latency-modes model "$@" ;;
  bench) start; python_run distributed/experiment.py "$@" ;;
  validate) start; python_run distributed/validate.py "$@" ;;
  *) echo 'Uso: distributed/run.sh {build|up|stop|status|smoke|bench|validate} [opciones]' >&2; exit 2 ;;
esac
