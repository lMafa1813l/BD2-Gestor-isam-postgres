#!/usr/bin/env bash
set -euo pipefail

here="$(cd "$(dirname "$0")" && pwd)"
root="$(dirname "$here")"

PSQL="${PSQL:?defina PSQL}"
PGBENCH="${PGBENCH:?defina PGBENCH}"
PGB_DB="${PGB_DB:?defina PGB_DB}"
WORKLOADS="${WORKLOADS:-/workloads}"
DATASETS_DIR="${DATASETS_DIR:-$root/datasets}"

N="${N:-200000}"
BATCHES="${BATCHES:-6}"
BATCH_ROWS="${BATCH_ROWS:-$((N / 5))}"
T="${T:-2}"
DATASET="${DATASET:-d3}"
CONFIGS="${CONFIGS:-btree isam60 isam80 isam100 isam80t25}"
OUT="${OUT:-$here/results/overflow_$(date +%Y%m%d_%H%M%S).csv}"
INSERT_MODE="${INSERT_MODE:-dist}"
WINDOW="${WINDOW:-100}"
LABEL="$DATASET-$INSERT_MODE"
if [ "$INSERT_MODE" = "narrow" ]; then
  HOTLO=$((N / 2))
  HOTW="$WINDOW"
  INSERT_SQL="SELECT $HOTLO + (random() * ($HOTW - 1))::int, repeat('p', 40) FROM generate_series(1, \$BATCH_ROWS)"
else
  HOTLO=1
  HOTW=$((N / 100))
  INSERT_SQL="SELECT CASE WHEN random() < 0.8 THEN 1 + (random() * ($N / 100 - 1))::int ELSE 1 + (random() * ($N - 1))::int END, repeat('p', 40) FROM generate_series(1, \$BATCH_ROWS)"
fi

mkdir -p "$(dirname "$OUT")"
echo "dataset,n,config,step,rows,insert_ms,reindex_ms,index_bytes,overflow_blocks,longest_chain,overflow_pct,buffers_eq_hot,eq_lat_ms" > "$OUT"

timed() {
  printf '\\timing on\n%s\n' "$1" | $PSQL | awk '/^Time:/ {print $2}' | tail -1
}

buffers() {
  $PSQL -c "EXPLAIN (ANALYZE, BUFFERS, TIMING OFF) $1" \
    | awk '/^ *Planning/ { exit } /Buffers:/ { gsub(/[^0-9]+/, " "); n = split($0, a, " "); for (i = 1; i <= n; i++) s += a[i]; print s; found = 1; exit } END { if (!found) print 0 }'
}

measure() {
  local cfg="$1" step="$2" rows="$3" ins_ms="$4" rei_ms="$5"
  local bytes stats ob lc op beq out lat
  bytes="$($PSQL -c "SELECT coalesce(pg_relation_size(to_regclass('bench_idx')), 0)")"
  case "$cfg" in
    isam*) stats="$($PSQL -c "SELECT overflow_blocks || ',' || longest_chain || ',' || round(overflow_pct::numeric, 2) FROM isam_index_stats('bench_idx')")" ;;
    *)     stats="0,0,0" ;;
  esac
  IFS=, read -r ob lc op <<< "$stats"
  beq="$(buffers "SELECT count(payload) FROM bench WHERE id = $((HOTLO + HOTW / 2))")"
  out="$($PGBENCH -n -c 1 -j 1 -T "$T" -D hotlo="$HOTLO" -D hotw="$HOTW" -f "$WORKLOADS/w6_eq_hot.pgb" "$PGB_DB" 2>&1)"
  lat="$(echo "$out" | awk '/^latency average =/ {print $4}')"
  echo "$LABEL,$N,$cfg,$step,$rows,$ins_ms,$rei_ms,$bytes,$ob,$lc,$op,$beq,$lat" | tee -a "$OUT"
}

for cfg in $CONFIGS; do
  echo ">> $DATASET / $cfg" >&2
  $PSQL -v n="$N" -f - < "$DATASETS_DIR/$DATASET.sql" > /dev/null

  fill=""; thr=""
  case "$cfg" in
    btree)
      $PSQL -c "CREATE INDEX bench_idx ON bench (id)" > /dev/null
      ;;
    isam*)
      if [[ "$cfg" =~ ^isam([0-9]+)(t([0-9]+))?$ ]]; then
        fill="${BASH_REMATCH[1]}"
        thr="${BASH_REMATCH[3]:-}"
      else
        echo "config invalida: $cfg" >&2; exit 1
      fi
      printf 'SET isam_am.fill_pct = %s;\nCREATE INDEX bench_idx ON bench USING isam_am (id);\n' "$fill" | $PSQL > /dev/null
      ;;
    *) echo "config invalida: $cfg" >&2; exit 1 ;;
  esac
  $PSQL -c "VACUUM ANALYZE bench" > /dev/null
  measure "$cfg" 0 0 0 0

  rows=0
  for b in $(seq 1 "$BATCHES"); do
    seed="$(printf '0.%02d' $((b + 10)))"
    ins_sql="${INSERT_SQL//\$BATCH_ROWS/$BATCH_ROWS}"
    ins_ms="$(timed "SELECT setseed($seed);
INSERT INTO bench $ins_sql;")"
    rows=$((rows + BATCH_ROWS))
    rei_ms=0
    if [ -n "$thr" ]; then
      need="$($PSQL -c "SELECT isam_reorg_needed('bench_idx', $thr)")"
      if [ "$need" = "t" ]; then
        rei_ms="$(timed "REINDEX INDEX bench_idx;")"
      fi
    fi
    $PSQL -c "ANALYZE bench" > /dev/null
    measure "$cfg" "$b" "$rows" "$ins_ms" "$rei_ms"
  done

  if [ -z "$thr" ]; then
    rei_ms="$(timed "REINDEX INDEX bench_idx;")"
    $PSQL -c "ANALYZE bench" > /dev/null
    measure "$cfg" reindex "$rows" 0 "$rei_ms"
  fi
done

echo >&2
echo "Resultados: $OUT" >&2
