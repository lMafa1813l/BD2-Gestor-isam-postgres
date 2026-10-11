\set ON_ERROR_STOP on
\set QUIET on
CREATE EXTENSION IF NOT EXISTS isam_am;
DROP TABLE IF EXISTS tc, tcu;
CREATE TABLE tc (id int, v text);
INSERT INTO tc SELECT (random() * 20000)::int - 10000, 'x' || g FROM generate_series(1, 50000) g;
CREATE INDEX tc_isam ON tc USING isam_am (id);
CHECKPOINT;
INSERT INTO tc SELECT (random() * 20000)::int - 10000, 'y' || g FROM generate_series(1, 5000) g;
INSERT INTO tc SELECT 500 + (random() * 20)::int, 's' || g FROM generate_series(1, 15000) g;
CREATE UNLOGGED TABLE tcu (id int, v text);
CREATE INDEX tcu_isam ON tcu USING isam_am (id);
INSERT INTO tcu SELECT g, 'u' || g FROM generate_series(1, 1000) g;
SELECT count(*) AS filas_tc_antes_de_la_caida FROM tc;
