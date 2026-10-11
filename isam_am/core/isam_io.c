#include "isam_platform.h"
#include <string.h>
#include "isam_io.h"

const char *isam_strerror(int code)
{
    switch (code) {
    case ISAM_OK:           return "ok";
    case ISAM_ERR_IO:       return "error de E/S";
    case ISAM_ERR_CORRUPT:  return "archivo ISAM corrupto";
    case ISAM_ERR_ARG:      return "argumento invalido";
    case ISAM_ERR_UNSORTED: return "las entradas de entrada no estan ordenadas por clave";
    case ISAM_ERR_FULL:     return "bloque lleno";
    default:                return "error desconocido";
    }
}

int isam_check_header(IsamBlockNo blk, IsamBlock *b)
{
    IsamBlockHeader *h = isam_hdr(b);
    if (h->blockno != blk || h->type < ISAM_BLK_META || h->type > ISAM_BLK_OVERFLOW)
        return ISAM_ERR_CORRUPT;
    return ISAM_OK;
}

int isam_write_meta(IsamFile *f)
{
    IsamBlock b;
    memset(&b, 0, sizeof(b));
    IsamBlockHeader *h = isam_hdr(&b);
    h->type = ISAM_BLK_META;
    h->blockno = 0;
    h->overflow_next = ISAM_INVALID_BLOCK;
    *isam_meta_in(&b) = f->meta;
    return isam_write_block(f, 0, &b);
}

int isam_sync(IsamFile *f)
{
    int rc = isam_write_meta(f);
    if (rc == ISAM_OK)
        f->meta_dirty = 0;
    return rc;
}

int isam_alloc_block(IsamFile *f, IsamBlockType type, uint32_t level, IsamBlockNo *out)
{
    IsamBlock b;
    memset(&b, 0, sizeof(b));
    IsamBlockNo blk = f->meta.n_blocks;
    IsamBlockHeader *h = isam_hdr(&b);
    h->type = (uint16_t) type;
    h->blockno = blk;
    h->overflow_next = ISAM_INVALID_BLOCK;
    h->level = level;
    int rc = isam_write_block(f, blk, &b);
    if (rc != ISAM_OK) return rc;
    f->meta.n_blocks++;
    if (type == ISAM_BLK_OVERFLOW) f->meta.n_overflow_blocks++;
    rc = isam_write_meta(f);
    if (rc != ISAM_OK) return rc;
    *out = blk;
    return ISAM_OK;
}
