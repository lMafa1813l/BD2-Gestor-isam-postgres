#!/usr/bin/env bash
set -euo pipefail

here="$(cd "$(dirname "$0")" && pwd)"
root="$(dirname "$here")"

PSQL="${PSQL:?defina PSQL, ej: PSQL='psql -X -q -At -U postgres -d bd2'}"
PGBENCH="${PGBENCH:?defina PGBENCH, ej: PGBENCH='pgbench -U postgres'}"
PGB_DB="${PGB_DB:?defina PGB_DB (base de datos de pgbench)}"
WORKLOADS="${WORKLOADS:-/workloads}"
DATASETS_DIR="${DATASETS_DIR:-$root/datasets}"

N="${N:-200000}"
T="${T:-5}"
CLIENTS="${CLIENTS:-4}"
REPS="${REPS:-1}"
FILL="${FILL:-80}"
MAINT_WORKERS="${MAINT_WORKERS:-}"
DATASETS="${DATASETS:-d1 d2 d3}"
CONFIGS="${CONFIGS:-none btree isam}"
OUT="${OUT:-$here/results/bench_$(date +%Y%m%d_%H%M%S).csv}"

mkdir -p "$(dirname "$OUT")"
echo "dataset,n,config,workload,rep,tps,lat_ms,build_ms,index_bytes,buffers_eq,buffers_range,overflow_blocks,longest_chain" > "$OUT"

domain() {
  case "$1" in
    d2) echo $((N / 10)) ;;
    *)  echo "$N" ;;
  esac
}

buffers() {
  $PSQL -c "EXPLAIN (ANALYZE, BUFFERS, TIMING OFF) $1" \
    | awk '/^ *Planning/ { exit } /Buffers:/ { gsub(/[^0-9]+/, " "); n = split($0, a, " "); for (i = 1; i <= n; i++) s += a[i]; print s; found = 1; exit } END { if (!found) print 0 }'
}

overflow_stats() {
  if [ "$1" = "isam" ]; then
    $PSQL -c "SELECT overflow_blocks || ',' || longest_chain FROM isam_index_stats('bench_idx')"
  else
    echo "0,0"
  fi
}

maint_prefix() {
  if [ -n "$MAINT_WORKERS" ]; then
    printf 'SET max_parallel_maintenance_workers = %s;\n' "$MAINT_WORKERS"
  fi
}

index_bytes() {
  $PSQL -c "SELECT coalesce(pg_relation_size(to_regclass('bench_idx')), 0)"
}

run_workload() {
  local ds="$1" cfg="$2" wl="$3" file="$4" dom="$5" span="$6" build_ms="$7" rep="$8"
  local out tps lat bytes beq brange mid ovf
  out="$($PGBENCH -n -c "$CLIENTS" -j "$CLIENTS" -T "$T" \
         -D n="$N" -D dom="$dom" -D span="$span" \
         -f "$WORKLOADS/$file" "$PGB_DB" 2>&1)"
  tps="$(echo "$out" | awk '/^tps =/ {print $3}')"
  lat="$(echo "$out" | awk '/^latency average =/ {print $4}')"
  if [ -z "$tps" ]; then
    echo "ERROR en pgbench ($ds/$cfg/$wl):" >&2
    echo "$out" >&2
    exit 1
  fi
  bytes="$(index_bytes)"
  ovf="$(overflow_stats "$cfg")"
  mid=$((dom / 2))
  beq="$(buffers "SELECT count(payload) FROM bench WHERE id = $mid")"
  brange="$(buffers "SELECT count(payload) FROM bench WHERE id BETWEEN $mid AND $((mid + span))")"
  echo "$ds,$N,$cfg,$wl,$rep,$tps,$lat,$build_ms,$bytes,$beq,$brange,$ovf" | tee -a "$OUT"
}

for ds in $DATASETS; do
  dom="$(domain "$ds")"
  span=$((dom / 1000))
  [ "$span" -lt 1 ] && span=1

  for cfg in $CONFIGS; do
    echo ">> $ds / $cfg: cargando $N filas" >&2
    $PSQL -v n="$N" -f - < "$DATASETS_DIR/$ds.sql" > /dev/null

    build_ms=0
    case "$cfg" in
      btree)
        build_ms="$( { printf '\\timing on\n'; maint_prefix; printf 'CREATE INDEX bench_idx ON bench (id);\n'; } | $PSQL | awk '/^Time:/ {print $2}' | tail -1)"
        ;;
      isam)
        build_ms="$( { printf '\\timing on\n'; maint_prefix; printf 'SET isam_am.fill_pct = %s;\nCREATE INDEX bench_idx ON bench USING isam_am (id);\n' "$FILL"; } | $PSQL | awk '/^Time:/ {print $2}' | tail -1)"
        ;;
      none) ;;
      *) echo "config desconocida: $cfg" >&2; exit 1 ;;
    esac
    $PSQL -c "VACUUM ANALYZE bench" > /dev/null

    for rep in $(seq 1 "$REPS"); do
      run_workload "$ds" "$cfg" w1_eq_uniform          w1_eq_uniform.pgb "$dom" "$span" "$build_ms" "$rep"
    done
    for rep in $(seq 1 "$REPS"); do
      run_workload "$ds" "$cfg" w2_eq_absent           w2_eq_absent.pgb  "$dom" "$span" "$build_ms" "$rep"
    done
    for rep in $(seq 1 "$REPS"); do
      run_workload "$ds" "$cfg" w5_eq_skew             w5_eq_skew.pgb    "$dom" "$span" "$build_ms" "$rep"
    done
    for rep in $(seq 1 "$REPS"); do
      run_workload "$ds" "$cfg" w4_range               w4_range.pgb      "$dom" "$span" "$build_ms" "$rep"
    done
    for rep in $(seq 1 "$REPS"); do
      run_workload "$ds" "$cfg" w3_insert              w3_insert.pgb     "$dom" "$span" "$build_ms" "$rep"
    done
    for rep in $(seq 1 "$REPS"); do
      run_workload "$ds" "$cfg" w1_eq_after_inserts    w1_eq_uniform.pgb "$dom" "$span" "$build_ms" "$rep"
    done
    for rep in $(seq 1 "$REPS"); do
      run_workload "$ds" "$cfg" w4_range_after_inserts w4_range.pgb      "$dom" "$span" "$build_ms" "$rep"
    done
  done
done

echo >&2
echo "Resultados: $OUT" >&2
if command -v column >/dev/null 2>&1; then
  column -s, -t "$OUT" >&2
fi
