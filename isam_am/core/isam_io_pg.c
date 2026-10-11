#include "isam_platform.h"
#include <string.h>
#include "access/generic_xlog.h"
#include "storage/bufpage.h"
#include "isam_io.h"

StaticAssertDecl(ISAM_BLOCK_SIZE == BLCKSZ, "ISAM_BLOCK_SIZE debe ser igual a BLCKSZ");
StaticAssertDecl(ISAM_BODY_OFFSET == SizeOfPageHeaderData, "ISAM_BODY_OFFSET debe ser SizeOfPageHeaderData");

void isam_rel_init(IsamFile *f, Relation rel)
{
    memset(f, 0, sizeof(*f));
    f->rel = rel;
}

void isam_pg_page_store(Page page, const IsamBlock *b)
{
    if (PageIsNew(page)) {
        PageInit(page, BLCKSZ, 0);
        ((PageHeader) page)->pd_lower = BLCKSZ;
        ((PageHeader) page)->pd_upper = BLCKSZ;
    }
    memcpy((char *) page + ISAM_BODY_OFFSET, b->raw + ISAM_BODY_OFFSET,
           BLCKSZ - ISAM_BODY_OFFSET);
}

int isam_open_rel(IsamFile *f, Relation rel)
{
    IsamBlock b;
    isam_rel_init(f, rel);
    if (RelationGetNumberOfBlocks(rel) == 0)
        return ISAM_ERR_CORRUPT;
    int rc = isam_read_block(f, 0, &b);
    if (rc != ISAM_OK)
        return rc;
    IsamMeta *m = isam_meta_in(&b);
    if (isam_hdr(&b)->type != ISAM_BLK_META || m->magic != ISAM_MAGIC ||
        m->version != ISAM_VERSION || m->block_size != ISAM_BLOCK_SIZE)
        return ISAM_ERR_CORRUPT;
    f->meta = *m;
    f->n_reads = 0;
    return ISAM_OK;
}

int isam_read_block(IsamFile *f, IsamBlockNo blk, IsamBlock *b)
{
    Buffer buf = ReadBuffer(f->rel, blk);
    LockBuffer(buf, BUFFER_LOCK_SHARE);
    memcpy(b->raw, BufferGetPage(buf), BLCKSZ);
    UnlockReleaseBuffer(buf);
    f->n_reads++;
    return isam_check_header(blk, b);
}

int isam_write_block(IsamFile *f, IsamBlockNo blk, const IsamBlock *b)
{
    Buffer buf;
    Page page;
    GenericXLogState *state;
    int flags = 0;

    if (blk >= RelationGetNumberOfBlocks(f->rel)) {
        flags = GENERIC_XLOG_FULL_IMAGE;
        for (;;) {
            buf = ExtendBufferedRel(BMR_REL(f->rel), MAIN_FORKNUM, NULL, EB_LOCK_FIRST);
            if (BufferGetBlockNumber(buf) >= blk)
                break;
            UnlockReleaseBuffer(buf);
        }
        if (BufferGetBlockNumber(buf) != blk) {
            UnlockReleaseBuffer(buf);
            return ISAM_ERR_CORRUPT;
        }
    } else {
        buf = ReadBuffer(f->rel, blk);
        LockBuffer(buf, BUFFER_LOCK_EXCLUSIVE);
    }

    state = GenericXLogStart(f->rel);
    page = GenericXLogRegisterBuffer(state, buf, flags);
    isam_pg_page_store(page, b);
    GenericXLogFinish(state);
    UnlockReleaseBuffer(buf);
    f->n_writes++;
    return ISAM_OK;
}

int isam_close(IsamFile *f)
{
    f->rel = NULL;
    return ISAM_OK;
}
