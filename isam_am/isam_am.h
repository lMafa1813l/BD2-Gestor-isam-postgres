#ifndef ISAM_AM_H
#define ISAM_AM_H

#include "postgres.h"

#include "access/amapi.h"
#include "access/genam.h"
#include "access/relscan.h"
#include "commands/vacuum.h"
#include "fmgr.h"
#include "nodes/execnodes.h"
#include "nodes/pathnodes.h"
#include "utils/rel.h"

#include "isam_core.h"

extern int isam_fill_pct;

extern void isam_am_error(Relation index, int rc);

extern IndexBuildResult *isam_ambuild(Relation heap, Relation index, IndexInfo *indexInfo);
extern void isam_ambuildempty(Relation index);
extern bool isam_aminsert(Relation indexRelation, Datum *values, bool *isnull,
                          ItemPointer heap_tid, Relation heapRelation,
                          IndexUniqueCheck checkUnique, bool indexUnchanged,
                          IndexInfo *indexInfo);
extern IndexBulkDeleteResult *isam_ambulkdelete(IndexVacuumInfo *info,
                                                IndexBulkDeleteResult *stats,
                                                IndexBulkDeleteCallback callback,
                                                void *callback_state);
extern IndexBulkDeleteResult *isam_amvacuumcleanup(IndexVacuumInfo *info,
                                                   IndexBulkDeleteResult *stats);
extern void isam_amcostestimate(PlannerInfo *root, IndexPath *path, double loop_count,
                                Cost *indexStartupCost, Cost *indexTotalCost,
                                Selectivity *indexSelectivity, double *indexCorrelation,
                                double *indexPages);
extern IndexScanDesc isam_ambeginscan(Relation r, int nkeys, int norderbys);
extern void isam_amrescan(IndexScanDesc scan, ScanKey scankey, int nscankeys,
                          ScanKey orderbys, int norderbys);
extern bool isam_amgettuple(IndexScanDesc scan, ScanDirection dir);
extern int64 isam_amgetbitmap(IndexScanDesc scan, TIDBitmap *tbm);
extern void isam_amendscan(IndexScanDesc scan);

#endif
