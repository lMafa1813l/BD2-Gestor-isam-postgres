#include "isam_platform.h"
#include <stdlib.h>
#include <string.h>
#include "isam_insert.h"

static int insert_sorted(IsamFile *f, IsamBlockNo blk, IsamBlock *b, IsamEntry entry)
{
    IsamBlockHeader *h = isam_hdr(b);
    IsamEntry *e = isam_entries(b);
    uint32_t pos = h->nentries;

    while (pos > 0 && e[pos - 1].key > entry.key) {
        e[pos] = e[pos - 1];
        pos--;
    }
    e[pos] = entry;
    h->nentries++;
    return isam_write_block(f, blk, b);
}

static int append_entry(IsamFile *f, IsamBlockNo blk, IsamBlock *b, IsamEntry entry)
{
    IsamBlockHeader *h = isam_hdr(b);
    isam_entries(b)[h->nentries++] = entry;
    return isam_write_block(f, blk, b);
}

static int find_tail(IsamFile *f, IsamBlockNo primary_next, IsamBlockNo *tail)
{
    IsamBlock b;
    IsamBlockNo cur = primary_next;
    uint32_t hops = 0;

    for (;;) {
        int rc = isam_read_block(f, cur, &b);
        if (rc != ISAM_OK)
            return rc;
        if (isam_hdr(&b)->type != ISAM_BLK_OVERFLOW)
            return ISAM_ERR_CORRUPT;
        if (isam_hdr(&b)->overflow_next == ISAM_INVALID_BLOCK)
            break;
        if (++hops > f->meta.n_blocks)
            return ISAM_ERR_CORRUPT;
        cur = isam_hdr(&b)->overflow_next;
    }
    *tail = cur;
    return ISAM_OK;
}

static int chain_insert(IsamFile *f, IsamBlockNo primary, IsamBlock *pb, IsamEntry entry)
{
    IsamBlock tb, nb_blk;
    IsamBlockHeader *ph = isam_hdr(pb);
    IsamBlockNo tail = ph->level;
    IsamBlockNo nb;
    int rc;

    if (tail == 0 && ph->overflow_next != ISAM_INVALID_BLOCK) {
        rc = find_tail(f, ph->overflow_next, &tail);
        if (rc != ISAM_OK)
            return rc;
    }

    if (tail != 0) {
        rc = isam_read_block(f, tail, &tb);
        if (rc != ISAM_OK)
            return rc;
        if (isam_hdr(&tb)->type != ISAM_BLK_OVERFLOW)
            return ISAM_ERR_CORRUPT;
        if (isam_hdr(&tb)->nentries < f->meta.data_capacity) {
            if (ph->level != tail) {
                ph->level = tail;
                rc = isam_write_block(f, primary, pb);
                if (rc != ISAM_OK)
                    return rc;
            }
            return append_entry(f, tail, &tb, entry);
        }
    }

    rc = isam_alloc_block(f, ISAM_BLK_OVERFLOW, 0, &nb);
    if (rc != ISAM_OK)
        return rc;

    memset(&nb_blk, 0, sizeof(nb_blk));
    isam_hdr(&nb_blk)->type = ISAM_BLK_OVERFLOW;
    isam_hdr(&nb_blk)->blockno = nb;
    isam_hdr(&nb_blk)->overflow_next = ISAM_INVALID_BLOCK;
    rc = append_entry(f, nb, &nb_blk, entry);
    if (rc != ISAM_OK)
        return rc;

    if (tail != 0) {
        isam_hdr(&tb)->overflow_next = nb;
        rc = isam_write_block(f, tail, &tb);
        if (rc != ISAM_OK)
            return rc;
    } else {
        ph->overflow_next = nb;
    }
    ph->level = nb;
    return isam_write_block(f, primary, pb);
}

int isam_insert(IsamFile *f, IsamEntry entry)
{
    IsamBlockNo blk;
    IsamBlock b;
    int rc = isam_index_descend(f, entry.key, ISAM_DESCEND_UPPER, &blk);
    if (rc != ISAM_OK)
        return rc;
    rc = isam_read_block(f, blk, &b);
    if (rc != ISAM_OK)
        return rc;
    if (isam_hdr(&b)->type != ISAM_BLK_DATA)
        return ISAM_ERR_CORRUPT;

    if (isam_hdr(&b)->nentries < f->meta.data_capacity)
        rc = insert_sorted(f, blk, &b, entry);
    else
        rc = chain_insert(f, blk, &b, entry);
    if (rc != ISAM_OK)
        return rc;

    f->meta.n_keys++;
    f->meta_dirty = 1;
    return ISAM_OK;
}

int isam_stats(IsamFile *f, IsamStats *st)
{
    IsamBlock b;
    uint64_t saved_reads = f->n_reads;
    uint32_t last = f->meta.first_data_block + f->meta.n_data_blocks;

    memset(st, 0, sizeof(*st));
    st->data_blocks = f->meta.n_data_blocks;
    st->overflow_blocks = f->meta.n_overflow_blocks;

    for (uint32_t blk = f->meta.first_data_block; blk < last; blk++) {
        uint32_t len = 0;
        int rc = isam_read_block(f, blk, &b);
        if (rc != ISAM_OK)
            return rc;
        st->n_keys += isam_hdr(&b)->nentries;
        IsamBlockNo next = isam_hdr(&b)->overflow_next;
        while (next != ISAM_INVALID_BLOCK) {
            if (++len > f->meta.n_blocks)
                return ISAM_ERR_CORRUPT;
            rc = isam_read_block(f, next, &b);
            if (rc != ISAM_OK)
                return rc;
            st->n_keys += isam_hdr(&b)->nentries;
            next = isam_hdr(&b)->overflow_next;
        }
        if (len > 0)
            st->chained_blocks++;
        if (len > st->longest_chain)
            st->longest_chain = len;
    }
    f->n_reads = saved_reads;
    return ISAM_OK;
}

int isam_needs_reorg(const IsamFile *f, uint32_t threshold_pct)
{
    return (uint64_t) f->meta.n_overflow_blocks * 100u >=
           (uint64_t) f->meta.n_data_blocks * threshold_pct;
}

#ifndef ISAM_IN_POSTGRES
int isam_reorganize(IsamFile *f, const char *path)
{
    uint64_t cap = f->meta.n_keys ? f->meta.n_keys : 1;
    uint64_t n = 0;
    uint32_t fill = f->meta.fill_pct;
    IsamEntry *all = ISAM_MALLOC(cap * sizeof(IsamEntry));
    IsamScan s;
    IsamBound none = { 0, 0, 0 };
    IsamEntry e;
    int rc;

    if (!all)
        return ISAM_ERR_IO;
    rc = isam_scan_begin(&s, f, none, none);
    if (rc != ISAM_OK) {
        ISAM_FREE(all);
        return rc;
    }
    while ((rc = isam_scan_next(&s, &e)) == 1) {
        if (n >= cap) {
            ISAM_FREE(all);
            return ISAM_ERR_CORRUPT;
        }
        all[n++] = e;
    }
    if (rc < 0) {
        ISAM_FREE(all);
        return rc;
    }

    isam_sort_entries(all, n);
    rc = isam_close(f);
    if (rc == ISAM_OK)
        rc = isam_build(f, path, all, n, fill);
    ISAM_FREE(all);
    return rc;
}
#endif
