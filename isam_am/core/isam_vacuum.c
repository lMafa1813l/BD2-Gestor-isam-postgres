#include "isam_platform.h"
#include <string.h>
#include "isam_vacuum.h"

static int compact_block(IsamFile *f, IsamBlockNo blk, IsamBlock *b,
                         IsamDeadFn dead, void *arg,
                         uint64_t *removed, uint64_t *remaining)
{
    IsamBlockHeader *h = isam_hdr(b);
    IsamEntry *e = isam_entries(b);
    uint32_t keep = 0;

    for (uint32_t i = 0; i < h->nentries; i++) {
        if (dead(&e[i], arg)) {
            (*removed)++;
            continue;
        }
        if (keep != i)
            e[keep] = e[i];
        keep++;
    }
    *remaining += keep;
    if (keep == h->nentries)
        return ISAM_OK;
    memset(&e[keep], 0, (h->nentries - keep) * sizeof(IsamEntry));
    h->nentries = (uint16_t) keep;
    return isam_write_block(f, blk, b);
}

int isam_delete_if(IsamFile *f, IsamDeadFn dead, void *arg,
                   uint64_t *removed, uint64_t *remaining)
{
    IsamBlock b;
    uint64_t rem = 0, left = 0;
    uint32_t last = f->meta.first_data_block + f->meta.n_data_blocks;

    for (uint32_t blk = f->meta.first_data_block; blk < last; blk++) {
        uint32_t hops = 0;
        IsamBlockNo cur = blk;
        for (;;) {
            int rc = isam_read_block(f, cur, &b);
            if (rc != ISAM_OK)
                return rc;
            rc = compact_block(f, cur, &b, dead, arg, &rem, &left);
            if (rc != ISAM_OK)
                return rc;
            cur = isam_hdr(&b)->overflow_next;
            if (cur == ISAM_INVALID_BLOCK)
                break;
            if (++hops > f->meta.n_blocks)
                return ISAM_ERR_CORRUPT;
        }
    }
    f->meta.n_keys = left;
    f->meta_dirty = 1;
    if (removed)
        *removed = rem;
    if (remaining)
        *remaining = left;
    return ISAM_OK;
}
