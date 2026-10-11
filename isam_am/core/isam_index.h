/* isam_index.h - Construcción del ISAM e índice de niveles (tareas 1.3 y 2.1). */
#ifndef ISAM_INDEX_H
#define ISAM_INDEX_H

#include "isam_io.h"

/* Ordena entradas por (key, tid_blk, tid_off). Útil antes de isam_build. */
void isam_sort_entries(IsamEntry *entries, uint64_t n);

#ifndef ISAM_IN_POSTGRES
int isam_build(IsamFile *f, const char *path, const IsamEntry *entries,
               uint64_t n, uint32_t fill_pct);
#endif

int isam_build_sorted(IsamFile *f, const IsamEntry *entries, uint64_t n, uint32_t fill_pct);
void isam_make_empty(IsamBlock *meta_blk, IsamBlock *data_blk, uint32_t fill_pct);

typedef enum IsamDescendMode {
    ISAM_DESCEND_LOWER,   /* bloque donde puede empezar `key` (última separador <  key): búsquedas */
    ISAM_DESCEND_UPPER    /* bloque donde se debe insertar `key` (último separador <= key): inserción */
} IsamDescendMode;

/* Desciende por los niveles del índice y devuelve el bloque DATA candidato. */
int isam_index_descend(IsamFile *f, IsamKey key, IsamDescendMode mode, IsamBlockNo *data_blk);

#endif
