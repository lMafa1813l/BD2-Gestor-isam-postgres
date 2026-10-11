#include "isam_am.h"

#include "utils/guc.h"

PG_MODULE_MAGIC;

PG_FUNCTION_INFO_V1(isam_handler);

int isam_fill_pct = ISAM_DEFAULT_FILL_PCT;

void _PG_init(void);

void
_PG_init(void)
{
    DefineCustomIntVariable("isam_am.fill_pct",
                            "Porcentaje de llenado de los bloques DATA al construir un indice ISAM.",
                            NULL,
                            &isam_fill_pct,
                            ISAM_DEFAULT_FILL_PCT,
                            ISAM_MIN_FILL_PCT,
                            100,
                            PGC_USERSET,
                            0,
                            NULL, NULL, NULL);
    MarkGUCPrefixReserved("isam_am");
}

void
isam_am_error(Relation index, int rc)
{
    ereport(ERROR,
            (errcode(rc == ISAM_ERR_CORRUPT ? ERRCODE_INDEX_CORRUPTED : ERRCODE_INTERNAL_ERROR),
             errmsg("isam_am: %s en el indice \"%s\"",
                    isam_strerror(rc), RelationGetRelationName(index))));
}

static bytea *
isam_amoptions(Datum reloptions, bool validate)
{
    if (validate && PointerIsValid(DatumGetPointer(reloptions)))
        ereport(ERROR,
                (errcode(ERRCODE_INVALID_PARAMETER_VALUE),
                 errmsg("isam_am no admite opciones de indice"),
                 errhint("Use SET isam_am.fill_pct antes de CREATE INDEX.")));
    return NULL;
}

static bool
isam_amvalidate(Oid opclassoid)
{
    return true;
}

Datum
isam_handler(PG_FUNCTION_ARGS)
{
    IndexAmRoutine *amroutine = makeNode(IndexAmRoutine);

    amroutine->amstrategies = 5;
    amroutine->amsupport = 1;
    amroutine->amoptsprocnum = 0;
    amroutine->amcanorder = false;
    amroutine->amcanorderbyop = false;
    amroutine->amcanbackward = false;
    amroutine->amcanunique = false;
    amroutine->amcanmulticol = false;
    amroutine->amoptionalkey = true;
    amroutine->amsearcharray = false;
    amroutine->amsearchnulls = false;
    amroutine->amstorage = false;
    amroutine->amclusterable = false;
    amroutine->ampredlocks = false;
    amroutine->amcanparallel = false;
#if PG_VERSION_NUM >= 170000
    amroutine->amcanbuildparallel = false;
#endif
    amroutine->amcaninclude = false;
    amroutine->amusemaintenanceworkmem = false;
    amroutine->amsummarizing = false;
    amroutine->amparallelvacuumoptions = 0;
    amroutine->amkeytype = InvalidOid;

    amroutine->ambuild = isam_ambuild;
    amroutine->ambuildempty = isam_ambuildempty;
    amroutine->aminsert = isam_aminsert;
    amroutine->ambulkdelete = isam_ambulkdelete;
    amroutine->amvacuumcleanup = isam_amvacuumcleanup;
    amroutine->amcanreturn = NULL;
    amroutine->amcostestimate = isam_amcostestimate;
    amroutine->amoptions = isam_amoptions;
    amroutine->amproperty = NULL;
    amroutine->ambuildphasename = NULL;
    amroutine->amvalidate = isam_amvalidate;
    amroutine->amadjustmembers = NULL;
    amroutine->ambeginscan = isam_ambeginscan;
    amroutine->amrescan = isam_amrescan;
    amroutine->amgettuple = isam_amgettuple;
    amroutine->amgetbitmap = isam_amgetbitmap;
    amroutine->amendscan = isam_amendscan;
    amroutine->ammarkpos = NULL;
    amroutine->amrestrpos = NULL;
    amroutine->amestimateparallelscan = NULL;
    amroutine->aminitparallelscan = NULL;
    amroutine->amparallelrescan = NULL;

    PG_RETURN_POINTER(amroutine);
}
