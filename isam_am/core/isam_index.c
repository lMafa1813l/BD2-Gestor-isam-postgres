#include "isam_platform.h"
#include <stdlib.h>
#include <string.h>
#include "isam_index.h"

static int cmp_entry(const void *a, const void *b)
{
    const IsamEntry *x = a, *y = b;
    if (x->key != y->key) return x->key < y->key ? -1 : 1;
    if (x->tid_blk != y->tid_blk) return x->tid_blk < y->tid_blk ? -1 : 1;
    if (x->tid_off != y->tid_off) return x->tid_off < y->tid_off ? -1 : 1;
    return 0;
}

void isam_sort_entries(IsamEntry *entries, uint64_t n)
{
    qsort(entries, n, sizeof(IsamEntry), cmp_entry);
}

static int check_input(const IsamEntry *entries, uint64_t n, uint32_t *fill_pct)
{
    if (*fill_pct == 0) *fill_pct = ISAM_DEFAULT_FILL_PCT;
    if (*fill_pct < ISAM_MIN_FILL_PCT || *fill_pct > 100) return ISAM_ERR_ARG;
    if (n > 0 && entries == NULL) return ISAM_ERR_ARG;
    for (uint64_t i = 1; i < n; i++)
        if (entries[i].key < entries[i - 1].key)
            return ISAM_ERR_UNSORTED;
    return ISAM_OK;
}

static void init_meta(IsamMeta *m, uint32_t fill_pct, uint64_t n, uint64_t D)
{
    memset(m, 0, sizeof(*m));
    m->magic = ISAM_MAGIC;
    m->version = ISAM_VERSION;
    m->block_size = ISAM_BLOCK_SIZE;
    m->key_type = 1;
    m->fill_pct = fill_pct;
    m->data_capacity = ISAM_DATA_CAPACITY;
    m->index_fanout = ISAM_INDEX_FANOUT;
    m->n_keys = n;
    m->first_data_block = 1;
    m->n_data_blocks = (uint32_t) D;
}

void isam_make_empty(IsamBlock *meta_blk, IsamBlock *data_blk, uint32_t fill_pct)
{
    IsamMeta m;
    if (fill_pct == 0) fill_pct = ISAM_DEFAULT_FILL_PCT;
    init_meta(&m, fill_pct, 0, 1);
    m.n_blocks = 2;
    m.root_block = 1;

    memset(data_blk, 0, sizeof(*data_blk));
    isam_hdr(data_blk)->type = ISAM_BLK_DATA;
    isam_hdr(data_blk)->blockno = 1;
    isam_hdr(data_blk)->overflow_next = ISAM_INVALID_BLOCK;

    memset(meta_blk, 0, sizeof(*meta_blk));
    isam_hdr(meta_blk)->type = ISAM_BLK_META;
    isam_hdr(meta_blk)->blockno = 0;
    isam_hdr(meta_blk)->overflow_next = ISAM_INVALID_BLOCK;
    *isam_meta_in(meta_blk) = m;
}

int isam_build_sorted(IsamFile *f, const IsamEntry *entries, uint64_t n, uint32_t fill_pct)
{
    int rc;
    IsamBlock blk;
    IsamKey *cur_keys = NULL, *next_keys = NULL;

    rc = check_input(entries, n, &fill_pct);
    if (rc != ISAM_OK) return rc;

    uint32_t per_block = (ISAM_DATA_CAPACITY * fill_pct) / 100;
    if (per_block < 1) per_block = 1;
    uint64_t D = n == 0 ? 1 : (n + per_block - 1) / per_block;
    if (D > 0x7FFFFFF0u) return ISAM_ERR_ARG;

    init_meta(&f->meta, fill_pct, n, D);
    rc = isam_write_meta(f);
    if (rc != ISAM_OK) return rc;

    cur_keys = ISAM_MALLOC(D * sizeof(IsamKey));
    if (!cur_keys) { rc = ISAM_ERR_IO; goto fail; }

    for (uint64_t i = 0; i < D; i++) {
        uint64_t start = i * per_block;
        uint64_t cnt = n > start ? (n - start < per_block ? n - start : per_block) : 0;
        memset(&blk, 0, sizeof(blk));
        IsamBlockHeader *h = isam_hdr(&blk);
        h->type = ISAM_BLK_DATA;
        h->nentries = (uint16_t) cnt;
        h->blockno = (uint32_t) (1 + i);
        h->overflow_next = ISAM_INVALID_BLOCK;
        if (cnt) memcpy(isam_entries(&blk), entries + start, cnt * sizeof(IsamEntry));
        cur_keys[i] = cnt ? entries[start].key : INT32_MIN;
        rc = isam_write_block(f, h->blockno, &blk);
        if (rc != ISAM_OK) goto fail;
    }

    uint64_t cur_n = D;
    IsamBlockNo child_first = 1;
    IsamBlockNo next_blk = (IsamBlockNo) (1 + D);
    uint32_t levels = 0;

    while (cur_n > 1) {
        if (levels >= ISAM_MAX_LEVELS) { rc = ISAM_ERR_ARG; goto fail; }
        uint64_t nb = (cur_n + ISAM_INDEX_FANOUT - 1) / ISAM_INDEX_FANOUT;
        next_keys = ISAM_MALLOC(nb * sizeof(IsamKey));
        if (!next_keys) { rc = ISAM_ERR_IO; goto fail; }

        f->meta.level_first[levels] = next_blk;
        f->meta.level_nblocks[levels] = (uint32_t) nb;

        for (uint64_t j = 0; j < nb; j++) {
            uint64_t start = j * ISAM_INDEX_FANOUT;
            uint64_t cnt = cur_n - start < ISAM_INDEX_FANOUT ? cur_n - start : ISAM_INDEX_FANOUT;
            memset(&blk, 0, sizeof(blk));
            IsamBlockHeader *h = isam_hdr(&blk);
            h->type = ISAM_BLK_INDEX;
            h->nentries = (uint16_t) cnt;
            h->blockno = next_blk + (IsamBlockNo) j;
            h->overflow_next = ISAM_INVALID_BLOCK;
            h->level = levels + 1;
            IsamIndexEntry *ie = isam_idx_entries(&blk);
            for (uint64_t k = 0; k < cnt; k++) {
                ie[k].key = cur_keys[start + k];
                ie[k].child = child_first + (IsamBlockNo) (start + k);
            }
            next_keys[j] = cur_keys[start];
            rc = isam_write_block(f, h->blockno, &blk);
            if (rc != ISAM_OK) goto fail;
        }
        ISAM_FREE(cur_keys);
        cur_keys = next_keys;
        next_keys = NULL;
        child_first = next_blk;
        next_blk += (IsamBlockNo) nb;
        cur_n = nb;
        levels++;
    }

    f->meta.n_index_levels = levels;
    f->meta.root_block = levels ? child_first : 1;
    f->meta.n_blocks = next_blk;

    rc = isam_write_meta(f);
    if (rc != ISAM_OK) goto fail;
    ISAM_FREE(cur_keys);
    return ISAM_OK;

fail:
    if (cur_keys) ISAM_FREE(cur_keys);
    if (next_keys) ISAM_FREE(next_keys);
    return rc;
}

#ifndef ISAM_IN_POSTGRES
int isam_build(IsamFile *f, const char *path, const IsamEntry *entries,
               uint64_t n, uint32_t fill_pct)
{
    int rc = check_input(entries, n, &fill_pct);
    if (rc != ISAM_OK) return rc;
    rc = isam_file_create(f, path);
    if (rc != ISAM_OK) return rc;
    rc = isam_build_sorted(f, entries, n, fill_pct);
    if (rc != ISAM_OK) isam_close(f);
    return rc;
}
#endif

/* Cantidad de separadores que cumplen la condición (búsqueda binaria). */
static uint32_t count_before(const IsamIndexEntry *e, uint32_t n, IsamKey key, IsamDescendMode mode)
{
    uint32_t lo = 0, hi = n;
    while (lo < hi) {
        uint32_t mid = lo + (hi - lo) / 2;
        int before = (mode == ISAM_DESCEND_LOWER) ? (e[mid].key < key) : (e[mid].key <= key);
        if (before) lo = mid + 1; else hi = mid;
    }
    return lo;
}

int isam_index_descend(IsamFile *f, IsamKey key, IsamDescendMode mode, IsamBlockNo *data_blk)
{
    IsamBlockNo blk = f->meta.root_block;
    IsamBlock b;

    for (uint32_t lvl = f->meta.n_index_levels; lvl >= 1; lvl--) {
        int rc = isam_read_block(f, blk, &b);
        if (rc != ISAM_OK) return rc;
        IsamBlockHeader *h = isam_hdr(&b);
        if (h->type != ISAM_BLK_INDEX || h->level != lvl || h->nentries == 0)
            return ISAM_ERR_CORRUPT;
        uint32_t idx = count_before(isam_idx_entries(&b), h->nentries, key, mode);
        blk = isam_idx_entries(&b)[idx == 0 ? 0 : idx - 1].child;
    }
    *data_blk = blk;
    return ISAM_OK;
}

int isam_index_range_blocks(IsamFile *f, IsamKey lo, IsamKey hi,
                            IsamBlockNo *first, IsamBlockNo *last)
{
    IsamBlockNo left = f->meta.root_block, right = left;
    IsamBlock a, b;

    for (uint32_t lvl = f->meta.n_index_levels; lvl >= 1; lvl--) {
        int rc = isam_read_block(f, left, &a);
        if (rc != ISAM_OK) return rc;
        if (right == left) {
            b = a;
        } else {
            rc = isam_read_block(f, right, &b);
            if (rc != ISAM_OK) return rc;
        }
        IsamBlockHeader *ah = isam_hdr(&a), *bh = isam_hdr(&b);
        if (ah->type != ISAM_BLK_INDEX || bh->type != ISAM_BLK_INDEX ||
            ah->level != lvl || bh->level != lvl ||
            ah->nentries == 0 || bh->nentries == 0)
            return ISAM_ERR_CORRUPT;
        uint32_t li = count_before(isam_idx_entries(&a), ah->nentries, lo, ISAM_DESCEND_LOWER);
        uint32_t ri = count_before(isam_idx_entries(&b), bh->nentries, hi, ISAM_DESCEND_UPPER);
        left = isam_idx_entries(&a)[li == 0 ? 0 : li - 1].child;
        right = isam_idx_entries(&b)[ri == 0 ? 0 : ri - 1].child;
    }
    *first = left;
    *last = right;
    return ISAM_OK;
}
