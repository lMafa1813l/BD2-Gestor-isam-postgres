\echo Use "ALTER EXTENSION isam_am UPDATE TO '1.1'" to load this file. \quit

CREATE FUNCTION isam_index_stats(index regclass,
                                 OUT n_keys bigint,
                                 OUT data_blocks int,
                                 OUT index_levels int,
                                 OUT overflow_blocks int,
                                 OUT chained_blocks int,
                                 OUT longest_chain int,
                                 OUT overflow_pct float8,
                                 OUT total_pages bigint)
RETURNS record
AS 'MODULE_PATHNAME', 'isam_index_stats'
LANGUAGE C STRICT;

CREATE FUNCTION isam_reorg_needed(index regclass, threshold_pct float8 DEFAULT 25)
RETURNS boolean
LANGUAGE sql STABLE
AS $$ SELECT overflow_pct >= threshold_pct FROM isam_index_stats(index) $$;
