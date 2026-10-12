\set ON_ERROR_STOP on
\if :{?allow_smoke}
\else
  \set allow_smoke false
\endif
SELECT 1 / CASE WHEN :n IN (100000,500000,1000000) OR :allow_smoke THEN 1 ELSE 0 END AS valid_size \gset
SET client_min_messages = warning;
SELECT setseed(0.42);
DROP TABLE IF EXISTS bench;
CREATE TABLE bench (id int, payload text);
INSERT INTO bench
-- Permutación aleatoria reproducible de 1..N: unicidad por construcción.
SELECT k, repeat('p', 40)
FROM (SELECT g AS k FROM generate_series(1, :n) g ORDER BY random()) s;
