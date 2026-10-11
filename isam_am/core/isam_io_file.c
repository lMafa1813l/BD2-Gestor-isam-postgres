#define _POSIX_C_SOURCE 200809L
#include <fcntl.h>
#include <unistd.h>
#include <string.h>
#include "isam_io.h"

int isam_file_create(IsamFile *f, const char *path)
{
    memset(f, 0, sizeof(*f));
    f->fd = open(path, O_RDWR | O_CREAT | O_TRUNC, 0644);
    return f->fd < 0 ? ISAM_ERR_IO : ISAM_OK;
}

int isam_read_block(IsamFile *f, IsamBlockNo blk, IsamBlock *b)
{
    ssize_t n = pread(f->fd, b->raw, ISAM_BLOCK_SIZE, (off_t) blk * ISAM_BLOCK_SIZE);
    if (n != ISAM_BLOCK_SIZE)
        return ISAM_ERR_IO;
    f->n_reads++;
    return isam_check_header(blk, b);
}

int isam_write_block(IsamFile *f, IsamBlockNo blk, const IsamBlock *b)
{
    ssize_t n = pwrite(f->fd, b->raw, ISAM_BLOCK_SIZE, (off_t) blk * ISAM_BLOCK_SIZE);
    if (n != ISAM_BLOCK_SIZE)
        return ISAM_ERR_IO;
    f->n_writes++;
    return ISAM_OK;
}

int isam_open(IsamFile *f, const char *path, int writable)
{
    IsamBlock b;
    memset(f, 0, sizeof(*f));
    f->fd = open(path, writable ? O_RDWR : O_RDONLY);
    if (f->fd < 0)
        return ISAM_ERR_IO;
    int rc = isam_read_block(f, 0, &b);
    if (rc != ISAM_OK) { close(f->fd); f->fd = -1; return rc; }
    IsamMeta *m = isam_meta_in(&b);
    if (isam_hdr(&b)->type != ISAM_BLK_META || m->magic != ISAM_MAGIC ||
        m->version != ISAM_VERSION || m->block_size != ISAM_BLOCK_SIZE) {
        close(f->fd); f->fd = -1;
        return ISAM_ERR_CORRUPT;
    }
    f->meta = *m;
    f->n_reads = 0;
    return ISAM_OK;
}

int isam_close(IsamFile *f)
{
    int rc = ISAM_OK;
    if (f->fd >= 0 && f->meta_dirty)
        rc = isam_sync(f);
    if (f->fd >= 0 && close(f->fd) != 0)
        rc = ISAM_ERR_IO;
    f->fd = -1;
    return rc;
}
