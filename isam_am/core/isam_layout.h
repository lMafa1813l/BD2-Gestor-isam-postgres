/*
 * isam_layout.h - Formato físico de bloques del ISAM (Bloque 2, tarea 1.2)
 *
 * Archivo = secuencia de bloques de ISAM_BLOCK_SIZE bytes (igual que la página
 * de PostgreSQL, para que en el Bloque 4 el mismo layout viva dentro de una
 * relación del AM sin cambios).
 *
 *   bloque 0                    META      (parámetros del índice)
 *   bloques 1 .. D              DATA      (área primaria, ordenada, contigua)
 *   bloques D+1 .. D+I          INDEX     (nivel 1, nivel 2, ... raíz al final)
 *   bloques > D+I               OVERFLOW  (se agregan al final; Bloque 3)
 *
 * Entrada de datos  : { key int32, tid (blk uint32, off uint16) }  = 12 bytes
 * Entrada de índice : { key int32 (primera clave del hijo), hijo uint32 } = 8 bytes
 *
 * Los enteros se guardan en el orden de bytes nativo (little-endian en x86/ARM).
 */
#ifndef ISAM_LAYOUT_H
#define ISAM_LAYOUT_H

#include <stdint.h>
#include <stddef.h>

#define ISAM_BLOCK_SIZE        8192
#ifdef ISAM_IN_POSTGRES
#define ISAM_BODY_OFFSET       24
#else
#define ISAM_BODY_OFFSET       0
#endif
#define ISAM_MAGIC             0x4D415349u   /* "ISAM" */
#define ISAM_VERSION           1u
#define ISAM_INVALID_BLOCK     0xFFFFFFFFu
#define ISAM_MAX_LEVELS        8
#define ISAM_DEFAULT_FILL_PCT  80            /* % de llenado de bloques DATA al construir */
#define ISAM_MIN_FILL_PCT      10

typedef int32_t  IsamKey;
typedef uint32_t IsamBlockNo;

typedef enum IsamBlockType {
    ISAM_BLK_META     = 1,
    ISAM_BLK_DATA     = 2,
    ISAM_BLK_INDEX    = 3,
    ISAM_BLK_OVERFLOW = 4
} IsamBlockType;

/* Cabecera común a todos los bloques (16 bytes) */
typedef struct IsamBlockHeader {
    uint16_t type;            /* IsamBlockType */
    uint16_t nentries;        /* entradas usadas */
    uint32_t blockno;         /* número del propio bloque (chequeo de sanidad) */
    uint32_t overflow_next;   /* DATA/OVERFLOW: siguiente bloque de la cadena, o ISAM_INVALID_BLOCK */
    uint32_t level;           /* INDEX: nivel (1 = apunta a DATA); DATA: ultimo bloque de su cadena de overflow (0 = sin cadena); OVERFLOW: 0 */
} IsamBlockHeader;

typedef struct IsamEntry {    /* entrada de DATA / OVERFLOW (12 bytes) */
    IsamKey  key;
    uint32_t tid_blk;         /* BlockNumber del heap de PostgreSQL */
    uint16_t tid_off;         /* OffsetNumber del heap */
    uint16_t reserved;
} IsamEntry;

typedef struct IsamIndexEntry { /* entrada de INDEX (8 bytes) */
    IsamKey     key;          /* primera clave del bloque hijo (separador) */
    IsamBlockNo child;
} IsamIndexEntry;

/* Contenido del bloque 0, a continuación de la cabecera */
typedef struct IsamMeta {
    uint32_t magic;
    uint32_t version;
    uint32_t block_size;
    uint32_t key_type;            /* 1 = int32 */
    uint32_t fill_pct;
    uint32_t data_capacity;       /* entradas por bloque DATA/OVERFLOW */
    uint32_t index_fanout;        /* entradas por bloque INDEX */
    uint32_t reserved;
    uint64_t n_keys;              /* entradas totales (primarias + overflow) */
    uint32_t n_blocks;            /* bloques totales del archivo, incluido el META */
    uint32_t first_data_block;    /* siempre 1 */
    uint32_t n_data_blocks;       /* D, >= 1 */
    uint32_t n_overflow_blocks;
    uint32_t n_index_levels;      /* 0 si D == 1 (no hace falta índice) */
    uint32_t root_block;          /* raíz del índice (o el único bloque DATA) */
    uint32_t level_first[ISAM_MAX_LEVELS];    /* primer bloque de cada nivel (0-based: nivel 1 en [0]) */
    uint32_t level_nblocks[ISAM_MAX_LEVELS];
} IsamMeta;

#define ISAM_HEADER_SIZE     16
#define ISAM_USABLE_BYTES    (ISAM_BLOCK_SIZE - ISAM_BODY_OFFSET - ISAM_HEADER_SIZE)
#define ISAM_DATA_CAPACITY   (ISAM_USABLE_BYTES / 12)
#define ISAM_INDEX_FANOUT    (ISAM_USABLE_BYTES / 8)

_Static_assert(sizeof(IsamBlockHeader) == ISAM_HEADER_SIZE, "header size");
_Static_assert(sizeof(IsamEntry) == 12, "entry size");
_Static_assert(sizeof(IsamIndexEntry) == 8, "index entry size");
_Static_assert(ISAM_DATA_CAPACITY  == ISAM_USABLE_BYTES / sizeof(IsamEntry), "data cap");
_Static_assert(ISAM_INDEX_FANOUT   == ISAM_USABLE_BYTES / sizeof(IsamIndexEntry), "fanout");
_Static_assert(ISAM_BODY_OFFSET + ISAM_HEADER_SIZE + sizeof(IsamMeta) <= ISAM_BLOCK_SIZE, "meta fits");
_Static_assert((ISAM_BODY_OFFSET + ISAM_HEADER_SIZE) % 8 == 0, "body alignment");

/* Buffer de un bloque, alineado a 8 bytes */
typedef union IsamBlock {
    uint8_t  raw[ISAM_BLOCK_SIZE];
    uint64_t align_;
} IsamBlock;

static inline IsamBlockHeader *isam_hdr(IsamBlock *b)        { return (IsamBlockHeader *) (b->raw + ISAM_BODY_OFFSET); }
static inline IsamEntry       *isam_entries(IsamBlock *b)    { return (IsamEntry *) (b->raw + ISAM_BODY_OFFSET + ISAM_HEADER_SIZE); }
static inline IsamIndexEntry  *isam_idx_entries(IsamBlock *b){ return (IsamIndexEntry *) (b->raw + ISAM_BODY_OFFSET + ISAM_HEADER_SIZE); }
static inline IsamMeta        *isam_meta_in(IsamBlock *b)    { return (IsamMeta *) (b->raw + ISAM_BODY_OFFSET + ISAM_HEADER_SIZE); }

#endif /* ISAM_LAYOUT_H */
