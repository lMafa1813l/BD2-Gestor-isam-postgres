\set ON_ERROR_STOP on
\set QUIET on
CREATE EXTENSION IF NOT EXISTS isam_am;
ALTER EXTENSION isam_am UPDATE;
DROP TABLE IF EXISTS bench;
CREATE TABLE bench (id int, payload text);
INSERT INTO bench SELECT (random() * 20000)::int + 1, repeat('p', 40) FROM generate_series(1, 20000);
CREATE INDEX bench_idx ON bench USING isam_am (id);
CHECKPOINT;
SELECT count(*) AS filas_iniciales FROM bench;
