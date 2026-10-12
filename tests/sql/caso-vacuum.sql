\set ON_ERROR_STOP on
\pset pager off
CREATE EXTENSION IF NOT EXISTS isam_am;
DROP TABLE IF EXISTS regression_vacuum;
CREATE TABLE regression_vacuum(id int, v text);
INSERT INTO regression_vacuum SELECT g, 'base' FROM generate_series(1,1358) g;
SET isam_am.fill_pct=100;
CREATE INDEX regression_vacuum_idx ON regression_vacuum USING isam_am(id);
RESET isam_am.fill_pct;
INSERT INTO regression_vacuum VALUES (680,'superviviente');
DELETE FROM regression_vacuum WHERE id=680 AND v='base';
VACUUM regression_vacuum;
SET enable_seqscan=off;
SET enable_bitmapscan=off;
EXPLAIN (COSTS OFF) SELECT v FROM regression_vacuum WHERE id=680;
SELECT v FROM regression_vacuum WHERE id=680;
DO $$ BEGIN
  ASSERT (SELECT count(*) FROM regression_vacuum WHERE id=680)=1,
         'VACUUM oculto la fila superviviente de overflow';
  ASSERT (SELECT count(*) FROM regression_vacuum WHERE id BETWEEN 679 AND 680)=2;
  ASSERT (SELECT count(*) FROM regression_vacuum WHERE id>679 AND id<681)=1;
  ASSERT (SELECT count(*) FROM regression_vacuum WHERE id=99999)=0;
END $$;
SET enable_indexscan=off;
SET enable_bitmapscan=on;
EXPLAIN (COSTS OFF) SELECT v FROM regression_vacuum WHERE id=680;
DO $$ BEGIN
  ASSERT (SELECT count(*) FROM regression_vacuum WHERE id=680)=1,
         'Bitmap scan omitio la fila superviviente';
END $$;
RESET enable_seqscan;
RESET enable_indexscan;
RESET enable_bitmapscan;
REINDEX INDEX regression_vacuum_idx;
SET enable_seqscan=off;
DO $$ BEGIN
  ASSERT (SELECT count(*) FROM regression_vacuum WHERE id=680)=1;
END $$;
RESET enable_seqscan;
DROP TABLE regression_vacuum;
\echo === separadores repetidos y pagina primaria vacia tras VACUUM
CREATE TABLE regression_vacuum(id int, v text);
INSERT INTO regression_vacuum SELECT g,'base' FROM generate_series(1,679) g;
INSERT INTO regression_vacuum SELECT 680,'base' FROM generate_series(1,1357);
INSERT INTO regression_vacuum VALUES (681,'base');
SET isam_am.fill_pct=100;
CREATE INDEX regression_vacuum_idx ON regression_vacuum USING isam_am(id);
RESET isam_am.fill_pct;
INSERT INTO regression_vacuum VALUES (680,'superviviente');
DELETE FROM regression_vacuum WHERE id=680 AND v='base';
VACUUM regression_vacuum;
SET enable_seqscan=off;
SET enable_bitmapscan=off;
DO $$ BEGIN
  ASSERT (SELECT count(*) FROM regression_vacuum WHERE id=680)=1,
         'Separadores repetidos o pagina vacia ocultaron el overflow';
  ASSERT (SELECT count(*) FROM regression_vacuum WHERE id BETWEEN 680 AND 681)=2;
END $$;
RESET enable_seqscan;
RESET enable_bitmapscan;
DROP TABLE regression_vacuum;
\echo OK: caso-vacuum.sql devuelve la fila superviviente por Index Scan y Bitmap Scan
