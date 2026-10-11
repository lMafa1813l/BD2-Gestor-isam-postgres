\set ON_ERROR_STOP on
\set QUIET on
DO $$
DECLARE a bigint; b bigint; sa bigint; sb bigint; n bigint;
BEGIN
  SELECT count(*) INTO n FROM bench;
  ASSERT n >= 20000, 'se perdieron filas de la carga inicial';
  PERFORM set_config('enable_seqscan', 'off', true);
  PERFORM set_config('enable_bitmapscan', 'off', true);
  SELECT count(*), coalesce(sum(id::bigint), 0) INTO a, b FROM bench WHERE id >= -100000;
  PERFORM set_config('enable_seqscan', 'on', true);
  PERFORM set_config('enable_indexscan', 'off', true);
  SELECT count(*), coalesce(sum(id::bigint), 0) INTO sa, sb FROM bench;
  ASSERT a = sa AND b = sb, format('indice (%s/%s) distinto del heap (%s/%s) tras la caida', a, b, sa, sb);
  RAISE NOTICE 'filas tras la caida: %, el indice coincide con el heap', n;
END $$;
\echo OK: caida bajo carga concurrente (WAL delta) correcta
