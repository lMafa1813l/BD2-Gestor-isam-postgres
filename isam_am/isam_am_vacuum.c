#include "isam_am.h"

#include "storage/lmgr.h"

typedef struct IsamVacState
{
    IndexBulkDeleteCallback callback;
    void       *callback_state;
} IsamVacState;

static int
isam_dead_entry(const IsamEntry *e, void *arg)
{
    IsamVacState *vs = (IsamVacState *) arg;
    ItemPointerData tid;

    ItemPointerSet(&tid, e->tid_blk, e->tid_off);
    return vs->callback(&tid, vs->callback_state) ? 1 : 0;
}

IndexBulkDeleteResult *
isam_ambulkdelete(IndexVacuumInfo *info, IndexBulkDeleteResult *stats,
                  IndexBulkDeleteCallback callback, void *callback_state)
{
    IsamFile    f;
    IsamVacState vs;
    uint64      removed = 0;
    uint64      remaining = 0;
    int         rc;

    if (stats == NULL)
        stats = (IndexBulkDeleteResult *) palloc0(sizeof(IndexBulkDeleteResult));

    vs.callback = callback;
    vs.callback_state = callback_state;

    LockRelationForExtension(info->index, ExclusiveLock);
    rc = isam_open_rel(&f, info->index);
    if (rc == ISAM_OK)
        rc = isam_delete_if(&f, isam_dead_entry, &vs, &removed, &remaining);
    UnlockRelationForExtension(info->index, ExclusiveLock);

    if (rc != ISAM_OK)
        isam_am_error(info->index, rc);

    stats->tuples_removed += (double) removed;
    stats->num_index_tuples = (double) remaining;
    stats->estimated_count = false;
    return stats;
}

IndexBulkDeleteResult *
isam_amvacuumcleanup(IndexVacuumInfo *info, IndexBulkDeleteResult *stats)
{
    if (info->analyze_only)
        return stats;

    if (stats == NULL)
    {
        stats = (IndexBulkDeleteResult *) palloc0(sizeof(IndexBulkDeleteResult));
        stats->num_index_tuples = info->num_heap_tuples;
        stats->estimated_count = true;
    }
    stats->num_pages = RelationGetNumberOfBlocks(info->index);
    return stats;
}
