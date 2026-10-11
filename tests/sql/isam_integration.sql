\set ON_ERROR_STOP on
\set QUIET on
\pset pager off

\echo == 1. extension
DROP EXTENSION IF EXISTS isam_am CASCADE;
CREATE EXTENSION isam_am;

CREATE OR REPLACE FUNCTION isam_fp(tbl text, pred text) RETURNS text LANGUAGE plpgsql AS $f$
DECLARE r text;
BEGIN
  EXECUTE format('SELECT count(*) || ''/'' || coalesce(sum(id::bigint), 0) || ''/'' || md5(coalesce(string_agg(v, '','' ORDER BY v), '''')) FROM %I WHERE %s', tbl, pred) INTO r;
  RETURN r;
END $f$;

CREATE OR REPLACE FUNCTION isam_uses_index(tbl text, idx text, pred text) RETURNS boolean LANGUAGE plpgsql AS $f$
DECLARE l text;
BEGIN
  FOR l IN EXECUTE format('EXPLAIN SELECT * FROM %I WHERE %s', tbl, pred) LOOP
    IF position(idx in l) > 0 THEN RETURN true; END IF;
  END LOOP;
  RETURN false;
END $f$;

CREATE OR REPLACE FUNCTION isam_assert(tbl text, idx text, pred text) RETURNS void LANGUAGE plpgsql AS $f$
DECLARE a text; b text;
BEGIN
  PERFORM set_config('enable_indexscan', 'off', true);
  PERFORM set_config('enable_bitmapscan', 'off', true);
  PERFORM set_config('enable_seqscan', 'on', true);
  a := isam_fp(tbl, pred);
  PERFORM set_config('enable_indexscan', 'on', true);
  PERFORM set_config('enable_bitmapscan', 'on', true);
  PERFORM set_config('enable_seqscan', 'off', true);
  b := isam_fp(tbl, pred);
  IF NOT isam_uses_index(tbl, idx, pred) THEN
    RAISE EXCEPTION 'el plan no usa % para: %', idx, pred;
  END IF;
  IF a IS DISTINCT FROM b THEN
    RAISE EXCEPTION 'resultado distinto para [%]: seqscan=% isam=%', pred, a, b;
  END IF;
END $f$;

CREATE OR REPLACE FUNCTION isam_assert_all(tbl text, idx text) RETURNS int LANGUAGE plpgsql AS $f$
DECLARE p text; n int := 0;
BEGIN
  FOREACH p IN ARRAY ARRAY[
    'id = 5', 'id = -9999', 'id = 123456', 'id = 0', 'id = 7010',
    'id < -9990', 'id <= 0', 'id > 9990', 'id >= 9999',
    'id BETWEEN -50 AND 50', 'id >= 100 AND id < 200', 'id > 5 AND id < 6',
    'id > 7000 AND id <= 7049', 'id >= -9000', 'id < 9000',
    'id = -2147483648', 'id = 2147483647', 'id >= 2147483647', 'id <= -2147483648',
    'id > 2147483646', 'id < -2147483647'
  ] LOOP
    PERFORM isam_assert(tbl, idx, p);
    n := n + 1;
  END LOOP;
  RETURN n;
END $f$;

\echo == 2. datos: 100k enteros con duplicados, negativos, extremos y NULLs
DROP TABLE IF EXISTS t;
CREATE TABLE t (id int, v text);
INSERT INTO t SELECT (random() * 20000)::int - 10000, 'x' || g FROM generate_series(1, 100000) g;
INSERT INTO t VALUES (-2147483648, 'min'), (2147483647, 'max'), (NULL, 'null1'), (NULL, 'null2');

\echo == 3. CREATE INDEX USING isam_am
CREATE INDEX t_isam ON t USING isam_am (id);
ANALYZE t;
SELECT pg_relation_size('t_isam') > 8192 * 100 AS indice_con_datos \gset
\if :indice_con_datos
\else
  \echo ERROR: el indice parece vacio
  \quit
\endif
SELECT isam_assert_all('t', 't_isam') || ' consultas coinciden con seqscan (tras build)' AS ok;

\echo == 4. el planner elige ISAM sin forzarlo
RESET enable_seqscan;
SELECT isam_uses_index('t', 't_isam', 'id = 5') AS usa_isam_igualdad \gset
\if :usa_isam_igualdad
\else
  \echo ERROR: el planner no eligio isam_am para igualdad
  \quit
\endif
EXPLAIN (COSTS OFF) SELECT * FROM t WHERE id = 5;
EXPLAIN (COSTS OFF) SELECT * FROM t WHERE id BETWEEN 10 AND 20;

\echo == 5. INSERT posteriores (uniformes, sesgados y extremos)
INSERT INTO t SELECT (random() * 20000)::int - 10000, 'u' || g FROM generate_series(1, 5000) g;
INSERT INTO t SELECT 7000 + (random() * 50)::int, 's' || g FROM generate_series(1, 20000) g;
INSERT INTO t VALUES (-2147483648, 'min2'), (2147483647, 'max2'), (NULL, 'null3'), (-100000, 'bajo'), (100000, 'alto');
SELECT isam_assert_all('t', 't_isam') || ' consultas coinciden (tras inserts con overflow)' AS ok;

\echo == 5b. estadisticas de overflow
DO $$
DECLARE s record;
BEGIN
  SELECT * INTO s FROM isam_index_stats('t_isam');
  ASSERT s.n_keys = (SELECT count(id) FROM t), 'n_keys no coincide con las filas indexables';
  ASSERT s.overflow_blocks > 0, 'deberia haber bloques de overflow';
  ASSERT s.longest_chain > 0, 'deberia haber cadena de overflow';
  ASSERT s.total_pages > s.data_blocks, 'total_pages incoherente';
  ASSERT isam_reorg_needed('t_isam', 0.1), 'deberia sugerir reorganizar con umbral bajo';
  ASSERT NOT isam_reorg_needed('t_isam', 100000), 'no deberia sugerir con umbral enorme';
END $$;
CREATE TABLE tb (id int);
CREATE INDEX tb_btree ON tb (id);
DO $$ BEGIN
  BEGIN
    PERFORM isam_index_stats('tb_btree');
    RAISE EXCEPTION 'debio fallar con un indice btree';
  EXCEPTION WHEN wrong_object_type THEN NULL;
  END;
END $$;
DROP TABLE tb;

\echo == 6. UPDATE y DELETE + VACUUM
UPDATE t SET id = id + 1 WHERE id BETWEEN 0 AND 100;
DELETE FROM t WHERE id BETWEEN 200 AND 400;
VACUUM t;
SELECT isam_assert_all('t', 't_isam') || ' consultas coinciden (tras update/delete/vacuum)' AS ok;
INSERT INTO t SELECT (random() * 20000)::int - 10000, 'v' || g FROM generate_series(1, 3000) g;
SELECT isam_assert_all('t', 't_isam') || ' consultas coinciden (insert tras vacuum)' AS ok;
VACUUM FULL t;
SELECT isam_assert_all('t', 't_isam') || ' consultas coinciden (tras vacuum full)' AS ok;

\echo == 7. REINDEX
REINDEX INDEX t_isam;
DO $$
DECLARE s record;
BEGIN
  SELECT * INTO s FROM isam_index_stats('t_isam');
  ASSERT s.overflow_blocks = 0 AND s.longest_chain = 0, 'REINDEX deberia eliminar el overflow';
  ASSERT s.n_keys = (SELECT count(id) FROM t), 'n_keys tras REINDEX';
END $$;
SELECT isam_assert_all('t', 't_isam') || ' consultas coinciden (tras reindex)' AS ok;

\echo == 8. fill_pct
SET isam_am.fill_pct = 100;
CREATE INDEX t_isam100 ON t USING isam_am (id);
RESET isam_am.fill_pct;
SELECT pg_relation_size('t_isam100') < pg_relation_size('t_isam') AS fill100_mas_compacto \gset
\if :fill100_mas_compacto
\else
  \echo ERROR: fill_pct=100 deberia ser mas compacto que el 80 por defecto
  \quit
\endif
SELECT isam_assert_all('t', 't_isam100') || ' consultas coinciden (indice fill 100)' AS ok;
DROP INDEX t_isam100;

\echo == 9. tabla UNLOGGED y TEMP
DROP TABLE IF EXISTS tu;
CREATE UNLOGGED TABLE tu (id int, v text);
INSERT INTO tu SELECT (random() * 20000)::int - 10000, 'x' || g FROM generate_series(1, 20000) g;
CREATE INDEX tu_isam ON tu USING isam_am (id);
INSERT INTO tu SELECT (random() * 20000)::int - 10000, 'y' || g FROM generate_series(1, 2000) g;
SELECT isam_assert_all('tu', 'tu_isam') || ' consultas coinciden (UNLOGGED)' AS ok;

CREATE TEMP TABLE tt (id int, v text);
INSERT INTO tt SELECT (random() * 20000)::int - 10000, 'x' || g FROM generate_series(1, 20000) g;
CREATE INDEX tt_isam ON tt USING isam_am (id);
INSERT INTO tt SELECT (random() * 20000)::int - 10000, 'y' || g FROM generate_series(1, 2000) g;
SELECT isam_assert_all('tt', 'tt_isam') || ' consultas coinciden (TEMP)' AS ok;

\echo == 10. tabla vacia, indice vacio y luego inserts
DROP TABLE IF EXISTS te;
CREATE TABLE te (id int, v text);
CREATE INDEX te_isam ON te USING isam_am (id);
INSERT INTO te SELECT (random() * 20000)::int - 10000, 'x' || g FROM generate_series(1, 5000) g;
ANALYZE te;
SELECT isam_assert_all('te', 'te_isam') || ' consultas coinciden (indice creado vacio)' AS ok;

\echo == 11. opciones no soportadas
DO $$ BEGIN
  BEGIN
    CREATE INDEX t_bad ON t USING isam_am (id) WITH (fillfactor = 50);
    RAISE EXCEPTION 'debio fallar';
  EXCEPTION WHEN others THEN
    IF SQLERRM = 'debio fallar' THEN RAISE; END IF;
  END;
END $$;

\echo == 12. limpieza
DROP INDEX t_isam;
DROP TABLE t, tu, te;
DROP EXTENSION isam_am CASCADE;
\echo OK: Bloque 4 (integracion ISAM + PostgreSQL) funciona
