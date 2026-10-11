\set ON_ERROR_STOP on
\set QUIET on
DO $$
DECLARE a bigint; b bigint;
BEGIN
  ASSERT (SELECT count(*) FROM tc) = 70000, 'tc perdio filas';
  ASSERT (SELECT count(*) FROM tcu) = 0, 'tcu deberia estar vacia tras la caida';

  PERFORM set_config('enable_seqscan', 'off', true);
  PERFORM set_config('enable_bitmapscan', 'off', true);
  SELECT count(*) INTO a FROM tc WHERE id = 510;
  SELECT count(*) INTO b FROM tc WHERE id BETWEEN 495 AND 525;
  PERFORM set_config('enable_seqscan', 'on', true);
  PERFORM set_config('enable_indexscan', 'off', true);
  ASSERT a = (SELECT count(*) FROM tc WHERE id = 510), 'igualdad distinta tras recovery';
  ASSERT b = (SELECT count(*) FROM tc WHERE id BETWEEN 495 AND 525), 'rango distinto tras recovery';
  PERFORM set_config('enable_indexscan', 'on', true);

  INSERT INTO tcu SELECT g, 'n' || g FROM generate_series(1, 500) g;
  PERFORM set_config('enable_seqscan', 'off', true);
  ASSERT (SELECT count(*) FROM tcu WHERE id >= 0) = 500, 'indice UNLOGGED invalido tras recovery';
  ASSERT (SELECT count(*) FROM tcu WHERE id = 7) = 1, 'igualdad UNLOGGED invalida tras recovery';
END $$;
DROP TABLE tc, tcu;
\echo OK: recuperacion tras caida correcta (WAL del indice y tabla UNLOGGED)
