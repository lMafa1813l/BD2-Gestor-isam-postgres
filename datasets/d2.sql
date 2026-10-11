\set ON_ERROR_STOP on
SET client_min_messages = warning;
SELECT setseed(0.42);
DROP TABLE IF EXISTS bench;
CREATE TABLE bench (id int, payload text);
INSERT INTO bench
SELECT 1 + (random() * (:n / 10 - 1))::int, repeat('p', 40)
FROM generate_series(1, :n);
