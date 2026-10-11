#include "isam_am.h"

#include "storage/lmgr.h"

bool
isam_aminsert(Relation indexRelation, Datum *values, bool *isnull,
              ItemPointer heap_tid, Relation heapRelation,
              IndexUniqueCheck checkUnique, bool indexUnchanged,
              IndexInfo *indexInfo)
{
    IsamFile    f;
    IsamEntry   e;
    int         rc;

    if (isnull[0])
        return false;

    e.key = DatumGetInt32(values[0]);
    e.tid_blk = ItemPointerGetBlockNumber(heap_tid);
    e.tid_off = ItemPointerGetOffsetNumber(heap_tid);
    e.reserved = 0;

    LockRelationForExtension(indexRelation, ExclusiveLock);
    rc = isam_open_rel(&f, indexRelation);
    if (rc == ISAM_OK)
        rc = isam_insert(&f, e);
    UnlockRelationForExtension(indexRelation, ExclusiveLock);

    if (rc != ISAM_OK)
        isam_am_error(indexRelation, rc);
    return false;
}
