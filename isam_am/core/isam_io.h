#ifndef ISAM_IO_H
#define ISAM_IO_H

#include "isam_platform.h"
#include <stdint.h>
#include "isam_layout.h"

#define ISAM_OK            0
#define ISAM_ERR_IO       (-1)
#define ISAM_ERR_CORRUPT  (-2)
#define ISAM_ERR_ARG      (-3)
#define ISAM_ERR_UNSORTED (-4)
#define ISAM_ERR_FULL     (-5)

typedef struct IsamFile {
#ifdef ISAM_IN_POSTGRES
    Relation rel;
#else
    int      fd;
#endif
    IsamMeta meta;
    uint64_t n_reads;
    uint64_t n_writes;
    int      meta_dirty;
} IsamFile;

const char *isam_strerror(int code);

#ifdef ISAM_IN_POSTGRES
void isam_rel_init(IsamFile *f, Relation rel);
int isam_open_rel(IsamFile *f, Relation rel);
void isam_pg_page_store(Page page, const IsamBlock *b);
#else
int isam_file_create(IsamFile *f, const char *path);
int isam_open(IsamFile *f, const char *path, int writable);
#endif
int isam_close(IsamFile *f);

int isam_check_header(IsamBlockNo blk, IsamBlock *b);
int isam_read_block(IsamFile *f, IsamBlockNo blk, IsamBlock *b);
int isam_write_block(IsamFile *f, IsamBlockNo blk, const IsamBlock *b);
int isam_write_meta(IsamFile *f);
int isam_sync(IsamFile *f);
int isam_alloc_block(IsamFile *f, IsamBlockType type, uint32_t level, IsamBlockNo *out);

#endif
