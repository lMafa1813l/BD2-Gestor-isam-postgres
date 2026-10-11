/* isam_search.h - Búsqueda por igualdad y rango (tarea 2.2). */
#ifndef ISAM_SEARCH_H
#define ISAM_SEARCH_H

#include <stddef.h>
#include "isam_index.h"

typedef struct IsamBound {
    int     present;     /* 0 = sin límite */
    int     inclusive;
    IsamKey key;
} IsamBound;

/*
 * Iterador de rango. Recorre bloques DATA consecutivos y, por cada uno, su
 * cadena de overflow. Dentro de un bloque las primarias salen ordenadas; las
 * de overflow salen en orden de cadena (no ordenadas).
 * Se declara en el stack del llamador (contiene un buffer de 8 KB).
 */
typedef struct IsamScan {
    IsamFile   *f;
    IsamBound   lo, hi;
    IsamBlockNo primary;       /* bloque DATA actual */
    IsamBlockNo last_data;
    IsamBlock   buf;           /* bloque cargado (primario o de overflow) */
    uint32_t    pos;
    uint32_t    chain_hops;
    int         in_chain;
    int         past_hi;       /* ya se pasó del límite superior en el bloque primario */
    int         done;
} IsamScan;

int isam_scan_begin(IsamScan *s, IsamFile *f, IsamBound lo, IsamBound hi);
/* 1 = devolvió una entrada, 0 = fin, <0 = error */
int isam_scan_next(IsamScan *s, IsamEntry *out);

/* Igualdad: copia hasta `max` coincidencias en `out`; *found = total de coincidencias. */
int isam_search_eq(IsamFile *f, IsamKey key, IsamEntry *out, size_t max, size_t *found);

/* Rango [lo, hi] inclusivo; cuenta las entradas (sirve para pruebas/benchmark). */
int isam_search_range_count(IsamFile *f, IsamKey lo, IsamKey hi, uint64_t *count);

#endif
