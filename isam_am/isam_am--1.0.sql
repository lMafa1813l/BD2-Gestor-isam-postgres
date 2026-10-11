-- isam_am--1.0.sql : registra el Access Method ISAM y su operator class para int4
\echo Use "CREATE EXTENSION isam_am" to load this file. \quit

CREATE FUNCTION isam_handler(internal)
RETURNS index_am_handler
AS 'MODULE_PATHNAME'
LANGUAGE C;

CREATE ACCESS METHOD isam_am TYPE INDEX HANDLER isam_handler;

-- Estrategias (mismos numeros que btree): 1 <, 2 <=, 3 =, 4 >=, 5 >
CREATE OPERATOR CLASS int4_ops
DEFAULT FOR TYPE int4 USING isam_am AS
    OPERATOR 1 <  (int4, int4),
    OPERATOR 2 <= (int4, int4),
    OPERATOR 3 =  (int4, int4),
    OPERATOR 4 >= (int4, int4),
    OPERATOR 5 >  (int4, int4),
    FUNCTION 1 btint4cmp(int4, int4);
