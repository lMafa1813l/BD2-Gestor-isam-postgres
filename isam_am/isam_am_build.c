#include "isam_am.h"

#include "access/tableam.h"
#include "access/xloginsert.h"
#include "miscadmin.h"
#include "storage/bufmgr.h"
#include "utils/memutils.h"

typedef struct IsamBuildState
{
    IsamEntry  *entries;
    uint64      n;
    uint64      cap;
} IsamBuildState;

static void
isam_build_callback(Relation index, ItemPointer tid, Datum *values,
                    bool *isnull, bool tupleIsAlive, void *state)
{
    IsamBuildState *st = (IsamBuildState *) state;
    IsamEntry  *e;

    if (isnull[0])
        return;

    if (st->n == st->cap)
    {
        st->cap *= 2;
        st->entries = (IsamEntry *) repalloc_huge(st->entries, st->cap * sizeof(IsamEntry));
    }
    e = &st->entries[st->n++];
    e->key = DatumGetInt32(values[0]);
    e->tid_blk = ItemPointerGetBlockNumber(tid);
    e->tid_off = ItemPointerGetOffsetNumber(tid);
    e->reserved = 0;
}

IndexBuildResult *
isam_ambuild(Relation heap, Relation index, IndexInfo *indexInfo)
{
    IsamBuildState st;
    IsamFile    f;
    IndexBuildResult *result;
    double      reltuples;
    int         rc;

    if (RelationGetNumberOfBlocks(index) != 0)
        elog(ERROR, "el indice \"%s\" ya contiene datos", RelationGetRelationName(index));

    st.n = 0;
    st.cap = 1024;
    st.entries = (IsamEntry *) palloc_extended(st.cap * sizeof(IsamEntry), MCXT_ALLOC_HUGE);

    reltuples = table_index_build_scan(heap, index, indexInfo, true, true,
                                       isam_build_callback, &st, NULL);

    isam_sort_entries(st.entries, st.n);
    isam_rel_init(&f, index);
    rc = isam_build_sorted(&f, st.entries, st.n, (uint32_t) isam_fill_pct);
    if (rc != ISAM_OK)
        isam_am_error(index, rc);

    result = (IndexBuildResult *) palloc(sizeof(IndexBuildResult));
    result->heap_tuples = reltuples;
    result->index_tuples = (double) st.n;
    pfree(st.entries);
    return result;
}

void
isam_ambuildempty(Relation index)
{
    IsamBlock  *blocks = (IsamBlock *) palloc(2 * sizeof(IsamBlock));

    isam_make_empty(&blocks[0], &blocks[1], (uint32_t) isam_fill_pct);

    for (int i = 0; i < 2; i++)
    {
        Buffer      buf = ExtendBufferedRel(BMR_REL(index), INIT_FORKNUM, NULL, EB_LOCK_FIRST);

        START_CRIT_SECTION();
        isam_pg_page_store(BufferGetPage(buf), &blocks[i]);
        MarkBufferDirty(buf);
        log_newpage_buffer(buf, true);
        END_CRIT_SECTION();
        UnlockReleaseBuffer(buf);
    }
    pfree(blocks);
}
