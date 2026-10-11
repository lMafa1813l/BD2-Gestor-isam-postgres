#ifndef ISAM_VACUUM_H
#define ISAM_VACUUM_H

#include "isam_insert.h"

typedef int (*IsamDeadFn)(const IsamEntry *entry, void *arg);

int isam_delete_if(IsamFile *f, IsamDeadFn dead, void *arg,
                   uint64_t *removed, uint64_t *remaining);

#endif
