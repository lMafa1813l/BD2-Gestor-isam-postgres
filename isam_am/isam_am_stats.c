#include "isam_am.h"

#include "access/htup_details.h"
#include "funcapi.h"

PG_FUNCTION_INFO_V1(isam_index_stats);

Datum
isam_index_stats(PG_FUNCTION_ARGS)
{
    Oid         relid = PG_GETARG_OID(0);
    Relation    index;
    IsamFile    f;
    IsamStats   st;
    TupleDesc   tupdesc;
    Datum       values[8];
    bool        nulls[8];
    HeapTuple   tuple;
    int         rc;

    if (get_call_result_type(fcinfo, NULL, &tupdesc) != TYPEFUNC_COMPOSITE)
        elog(ERROR, "isam_index_stats: tipo de retorno no compuesto");
    tupdesc = BlessTupleDesc(tupdesc);

    index = index_open(relid, AccessShareLock);
    if (index->rd_indam->ambuild != isam_ambuild)
        ereport(ERROR,
                (errcode(ERRCODE_WRONG_OBJECT_TYPE),
                 errmsg("\"%s\" no es un indice isam_am", RelationGetRelationName(index))));

    rc = isam_open_rel(&f, index);
    if (rc == ISAM_OK)
        rc = isam_stats(&f, &st);
    if (rc != ISAM_OK)
        isam_am_error(index, rc);

    memset(nulls, 0, sizeof(nulls));
    values[0] = Int64GetDatum((int64) st.n_keys);
    values[1] = Int32GetDatum((int32) st.data_blocks);
    values[2] = Int32GetDatum((int32) f.meta.n_index_levels);
    values[3] = Int32GetDatum((int32) st.overflow_blocks);
    values[4] = Int32GetDatum((int32) st.chained_blocks);
    values[5] = Int32GetDatum((int32) st.longest_chain);
    values[6] = Float8GetDatum(100.0 * (double) st.overflow_blocks / (double) st.data_blocks);
    values[7] = Int64GetDatum((int64) RelationGetNumberOfBlocks(index));

    index_close(index, AccessShareLock);
    tuple = heap_form_tuple(tupdesc, values, nulls);
    PG_RETURN_DATUM(HeapTupleGetDatum(tuple));
}
