\set ON_ERROR_STOP on
SET client_min_messages = warning;
SELECT setseed(0.42);
DROP TABLE IF EXISTS bench;
CREATE TABLE bench (id int, payload text);
INSERT INTO bench
SELECT k, repeat('p', 40)
FROM (SELECT g AS k FROM generate_series(1, :n) g ORDER BY random()) s;
