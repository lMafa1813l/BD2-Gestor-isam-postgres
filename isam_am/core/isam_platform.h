#ifndef ISAM_PLATFORM_H
#define ISAM_PLATFORM_H

#ifdef ISAM_IN_POSTGRES
#include "postgres.h"
#include "storage/bufmgr.h"
#include "utils/rel.h"
#define ISAM_MALLOC(n) palloc(n)
#define ISAM_FREE(p)   pfree(p)
#else
#include <stdlib.h>
#define ISAM_MALLOC(n) malloc(n)
#define ISAM_FREE(p)   free(p)
#endif

#endif
