#include "isam_am.h"

#include "access/skey.h"
#include "nodes/tidbitmap.h"

typedef struct IsamScanOpaque
{
    IsamFile    f;
    IsamScan    s;
    IsamBound   lo;
    IsamBound   hi;
    bool        ready;
    bool        begun;
    bool        empty;
} IsamScanOpaque;

IndexScanDesc
isam_ambeginscan(Relation r, int nkeys, int norderbys)
{
    IndexScanDesc scan = RelationGetIndexScan(r, nkeys, norderbys);
    IsamScanOpaque *so = (IsamScanOpaque *) palloc0(sizeof(IsamScanOpaque));

    scan->opaque = so;
    return scan;
}

static void
tighten_lo(IsamBound *lo, IsamKey key, bool inclusive)
{
    if (!lo->present || key > lo->key ||
        (key == lo->key && !inclusive && lo->inclusive))
    {
        lo->present = 1;
        lo->key = key;
        lo->inclusive = inclusive;
    }
}

static void
tighten_hi(IsamBound *hi, IsamKey key, bool inclusive)
{
    if (!hi->present || key < hi->key ||
        (key == hi->key && !inclusive && hi->inclusive))
    {
        hi->present = 1;
        hi->key = key;
        hi->inclusive = inclusive;
    }
}

void
isam_amrescan(IndexScanDesc scan, ScanKey scankey, int nscankeys,
              ScanKey orderbys, int norderbys)
{
    IsamScanOpaque *so = (IsamScanOpaque *) scan->opaque;
    IsamBound   lo = {0, 0, 0};
    IsamBound   hi = {0, 0, 0};

    so->ready = false;
    so->begun = false;
    so->empty = false;

    if (scankey && scan->numberOfKeys > 0)
        memmove(scan->keyData, scankey, scan->numberOfKeys * sizeof(ScanKeyData));

    for (int i = 0; i < scan->numberOfKeys; i++)
    {
        ScanKey     sk = &scan->keyData[i];
        IsamKey     k;

        if (sk->sk_flags & SK_ISNULL)
        {
            so->empty = true;
            return;
        }
        k = DatumGetInt32(sk->sk_argument);

        switch (sk->sk_strategy)
        {
            case 1:
                tighten_hi(&hi, k, false);
                break;
            case 2:
                tighten_hi(&hi, k, true);
                break;
            case 3:
                tighten_lo(&lo, k, true);
                tighten_hi(&hi, k, true);
                break;
            case 4:
                tighten_lo(&lo, k, true);
                break;
            case 5:
                tighten_lo(&lo, k, false);
                break;
            default:
                elog(ERROR, "isam_am: estrategia %d no soportada", sk->sk_strategy);
        }
    }

    so->lo = lo;
    so->hi = hi;
    so->ready = true;
}

static void
isam_begin_if_needed(IndexScanDesc scan, IsamScanOpaque *so)
{
    int         rc;

    if (so->begun)
        return;
    rc = isam_open_rel(&so->f, scan->indexRelation);
    if (rc == ISAM_OK)
        rc = isam_scan_begin(&so->s, &so->f, so->lo, so->hi);
    if (rc != ISAM_OK)
        isam_am_error(scan->indexRelation, rc);
    so->begun = true;
}

bool
isam_amgettuple(IndexScanDesc scan, ScanDirection dir)
{
    IsamScanOpaque *so = (IsamScanOpaque *) scan->opaque;
    IsamEntry   e;
    int         rc;

    if (so->empty || !so->ready)
        return false;
    if (!ScanDirectionIsForward(dir))
        elog(ERROR, "isam_am solo admite recorridos hacia adelante");
    isam_begin_if_needed(scan, so);

    rc = isam_scan_next(&so->s, &e);
    if (rc < 0)
        isam_am_error(scan->indexRelation, rc);
    if (rc == 0)
        return false;

    ItemPointerSet(&scan->xs_heaptid, e.tid_blk, e.tid_off);
    scan->xs_recheck = false;
    return true;
}

int64
isam_amgetbitmap(IndexScanDesc scan, TIDBitmap *tbm)
{
    IsamScanOpaque *so = (IsamScanOpaque *) scan->opaque;
    IsamEntry   e;
    int64       ntids = 0;
    int         rc;

    if (so->empty || !so->ready)
        return 0;
    isam_begin_if_needed(scan, so);

    while ((rc = isam_scan_next(&so->s, &e)) == 1)
    {
        ItemPointerData tid;

        ItemPointerSet(&tid, e.tid_blk, e.tid_off);
        tbm_add_tuples(tbm, &tid, 1, false);
        ntids++;
    }
    if (rc < 0)
        isam_am_error(scan->indexRelation, rc);
    return ntids;
}

void
isam_amendscan(IndexScanDesc scan)
{
    IsamScanOpaque *so = (IsamScanOpaque *) scan->opaque;

    if (so)
        pfree(so);
    scan->opaque = NULL;
}
