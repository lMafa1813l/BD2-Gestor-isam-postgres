\set ON_ERROR_STOP on
\pset pager off
\echo === 1. version y extension
SELECT version();
CREATE EXTENSION IF NOT EXISTS isam_am;
CREATE SCHEMA IF NOT EXISTS demo_isam;
DROP TABLE IF EXISTS demo_isam.items;
CREATE TABLE demo_isam.items(id int, payload text);
INSERT INTO demo_isam.items SELECT g,'base' FROM generate_series(1,1358) g;
SET isam_am.fill_pct=100;
CREATE INDEX items_idx ON demo_isam.items USING isam_am(id);
ANALYZE demo_isam.items;
\echo === 2. igualdad exitosa, ausente y rango; mostrar uso real del indice
SET enable_seqscan=off;
SET enable_bitmapscan=off;
EXPLAIN (ANALYZE, BUFFERS, COSTS OFF) SELECT * FROM demo_isam.items WHERE id=680;
SELECT * FROM demo_isam.items WHERE id=680;
SELECT count(*) AS ausencia_debe_ser_cero FROM demo_isam.items WHERE id=99999;
SELECT id FROM demo_isam.items WHERE id BETWEEN 676 AND 684 ORDER BY id;
\echo === 3. insertar la superviviente y producir una cadena larga
INSERT INTO demo_isam.items VALUES (680,'superviviente');
INSERT INTO demo_isam.items SELECT 700,'overflow-'||g FROM generate_series(1,10000) g;
SELECT * FROM isam_index_stats('demo_isam.items_idx');
SELECT isam_reorg_needed('demo_isam.items_idx',25) AS sugerencia;
\echo === 4. DELETE + VACUUM: superviviente debe aparecer sin REINDEX
DELETE FROM demo_isam.items WHERE id=680 AND payload='base';
VACUUM demo_isam.items;
EXPLAIN (ANALYZE, BUFFERS, COSTS OFF) SELECT payload FROM demo_isam.items WHERE id=680;
SELECT payload FROM demo_isam.items WHERE id=680;
DO $$ BEGIN
  ASSERT (SELECT count(*) FROM demo_isam.items WHERE id=680)=1;
  ASSERT (SELECT payload FROM demo_isam.items WHERE id=680)='superviviente';
  ASSERT (SELECT count(*) FROM demo_isam.items WHERE id=700)=10001;
END $$;
\echo === 5. REINDEX elimina overflow manteniendo relleno 100
REINDEX INDEX demo_isam.items_idx;
SELECT * FROM isam_index_stats('demo_isam.items_idx');
DO $$ BEGIN
  ASSERT (SELECT overflow_blocks FROM isam_index_stats('demo_isam.items_idx'))=0;
  ASSERT (SELECT count(*) FROM demo_isam.items WHERE id=680)=1;
END $$;
RESET isam_am.fill_pct;
RESET enable_seqscan;
RESET enable_bitmapscan;
\echo OK: demo completa; tabla conservada en demo_isam.items para preguntas en vivo
