#ifndef ISAM_INSERT_H
#define ISAM_INSERT_H

#include "isam_search.h"

typedef struct IsamStats {
    uint64_t n_keys;
    uint32_t data_blocks;
    uint32_t overflow_blocks;
    uint32_t longest_chain;
    uint32_t chained_blocks;
} IsamStats;

int isam_insert(IsamFile *f, IsamEntry entry);
int isam_stats(IsamFile *f, IsamStats *st);
int isam_needs_reorg(const IsamFile *f, uint32_t threshold_pct);
#ifndef ISAM_IN_POSTGRES
int isam_reorganize(IsamFile *f, const char *path);
#endif

#endif
