\set ON_ERROR_STOP on
SET client_min_messages = warning;
SELECT setseed(0.42);
DROP TABLE IF EXISTS bench;
CREATE TABLE bench (id int, payload text);
INSERT INTO bench
SELECT CASE WHEN random() < 0.8
            THEN 1 + (random() * (:n / 100 - 1))::int
            ELSE 1 + (random() * (:n - 1))::int END,
       repeat('p', 40)
FROM generate_series(1, :n);
