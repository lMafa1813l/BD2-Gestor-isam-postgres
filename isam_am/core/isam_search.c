#include "isam_platform.h"
#include <string.h>
#include "isam_search.h"

static int below_lo(const IsamScan *s, IsamKey k)
{
    return s->lo.present && (k < s->lo.key || (k == s->lo.key && !s->lo.inclusive));
}
static int above_hi(const IsamScan *s, IsamKey k)
{
    return s->hi.present && (k > s->hi.key || (k == s->hi.key && !s->hi.inclusive));
}

int isam_scan_begin(IsamScan *s, IsamFile *f, IsamBound lo, IsamBound hi)
{
    int rc;
    memset(&s->buf, 0, sizeof(s->buf));
    s->f = f;
    s->lo = lo;
    s->hi = hi;
    s->pos = 0;
    s->chain_hops = 0;
    s->in_chain = 0;
    s->past_hi = 0;
    s->done = 0;
    s->last_data = f->meta.first_data_block + f->meta.n_data_blocks - 1;

    if (lo.present) {
        rc = isam_index_descend(f, lo.key, ISAM_DESCEND_LOWER, &s->primary);
        if (rc != ISAM_OK) return rc;
    } else {
        s->primary = f->meta.first_data_block;
    }
    rc = isam_read_block(f, s->primary, &s->buf);
    if (rc != ISAM_OK) return rc;
    if (isam_hdr(&s->buf)->type != ISAM_BLK_DATA) return ISAM_ERR_CORRUPT;

    if (lo.present) {   /* salto binario a la primera clave >= lo dentro del bloque */
        IsamEntry *e = isam_entries(&s->buf);
        uint32_t a = 0, b = isam_hdr(&s->buf)->nentries;
        while (a < b) {
            uint32_t m = a + (b - a) / 2;
            if (e[m].key < lo.key) a = m + 1; else b = m;
        }
        s->pos = a;
    }
    return ISAM_OK;
}

int isam_scan_next(IsamScan *s, IsamEntry *out)
{
    int rc;
    while (!s->done) {
        IsamBlockHeader *h = isam_hdr(&s->buf);
        IsamEntry *e = isam_entries(&s->buf);

        while (s->pos < h->nentries) {
            IsamEntry cur = e[s->pos++];
            if (!s->in_chain) {
                if (below_lo(s, cur.key)) continue;
                if (above_hi(s, cur.key)) {      /* el resto del bloque primario está ordenado: también pasa */
                    s->past_hi = 1;
                    s->pos = h->nentries;
                    break;
                }
            } else if (below_lo(s, cur.key) || above_hi(s, cur.key)) {
                continue;                        /* overflow no ordenado: solo filtrar */
            }
            *out = cur;
            return 1;
        }

        /* bloque agotado: cadena de overflow del mismo bloque primario */
        if (h->overflow_next != ISAM_INVALID_BLOCK) {
            if (++s->chain_hops > s->f->meta.n_blocks) return ISAM_ERR_CORRUPT;
            rc = isam_read_block(s->f, h->overflow_next, &s->buf);
            if (rc != ISAM_OK) return rc;
            if (isam_hdr(&s->buf)->type != ISAM_BLK_OVERFLOW) return ISAM_ERR_CORRUPT;
            s->in_chain = 1;
            s->pos = 0;
            continue;
        }

        if (s->past_hi || s->primary >= s->last_data) {
            s->done = 1;
            return 0;
        }

        /* siguiente bloque primario (secuencial, contiguo en disco) */
        s->primary++;
        s->chain_hops = 0;
        rc = isam_read_block(s->f, s->primary, &s->buf);
        if (rc != ISAM_OK) return rc;
        if (isam_hdr(&s->buf)->type != ISAM_BLK_DATA) return ISAM_ERR_CORRUPT;
        s->in_chain = 0;
        s->pos = 0;
        /*
         * Invariante ISAM: toda entrada de un bloque (y de su overflow) es >= a
         * su primera clave primaria (el separador). Si esa clave ya supera el
         * límite superior, ni el bloque ni su cadena pueden aportar más.
         */
        h = isam_hdr(&s->buf);
        if (h->nentries > 0 && above_hi(s, isam_entries(&s->buf)[0].key)) {
            s->done = 1;
            return 0;
        }
    }
    return 0;
}

int isam_search_eq(IsamFile *f, IsamKey key, IsamEntry *out, size_t max, size_t *found)
{
    IsamScan s;
    IsamBound b = { 1, 1, key };
    IsamEntry e;
    size_t n = 0;
    int rc = isam_scan_begin(&s, f, b, b);
    if (rc != ISAM_OK) return rc;
    while ((rc = isam_scan_next(&s, &e)) == 1) {
        if (out && n < max) out[n] = e;
        n++;
    }
    if (rc < 0) return rc;
    if (found) *found = n;
    return ISAM_OK;
}

int isam_search_range_count(IsamFile *f, IsamKey lo, IsamKey hi, uint64_t *count)
{
    IsamScan s;
    IsamBound l = { 1, 1, lo }, h = { 1, 1, hi };
    IsamEntry e;
    uint64_t n = 0;
    int rc = isam_scan_begin(&s, f, l, h);
    if (rc != ISAM_OK) return rc;
    while ((rc = isam_scan_next(&s, &e)) == 1) n++;
    if (rc < 0) return rc;
    *count = n;
    return ISAM_OK;
}
