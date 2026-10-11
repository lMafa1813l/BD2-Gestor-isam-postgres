#include "isam_am.h"

#include "utils/selfuncs.h"

void
isam_amcostestimate(PlannerInfo *root, IndexPath *path, double loop_count,
                    Cost *indexStartupCost, Cost *indexTotalCost,
                    Selectivity *indexSelectivity, double *indexCorrelation,
                    double *indexPages)
{
    GenericCosts costs;

    MemSet(&costs, 0, sizeof(costs));
    genericcostestimate(root, path, loop_count, &costs);

    *indexStartupCost = costs.indexStartupCost;
    *indexTotalCost = costs.indexTotalCost;
    *indexSelectivity = costs.indexSelectivity;
    *indexCorrelation = 0.0;
    *indexPages = costs.numIndexPages;
}
