#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include "isam_core.h"

static int fails = 0, checks = 0;
#define CHECK(c) do { checks++; if (!(c)) { fails++; printf("  FALLO %s:%d: %s\n", __FILE__, __LINE__, #c); } } while (0)

static uint64_t rng_s = 88172645463325252ull;
static uint64_t rnd(void) { rng_s ^= rng_s << 13; rng_s ^= rng_s >> 7; rng_s ^= rng_s << 17; return rng_s; }

typedef struct Ref {
    IsamEntry *a;
    uint64_t n;
} Ref;

static IsamEntry mk(IsamKey k, uint32_t i)
{
    IsamEntry e = { k, i, (uint16_t) (i % 100 + 1), 0 };
    return e;
}

static Ref ref_new(uint64_t cap)
{
    Ref r = { malloc(cap * sizeof(IsamEntry)), 0 };
    return r;
}

static int cmp_u32(const void *a, const void *b)
{
    uint32_t x = *(const uint32_t *) a, y = *(const uint32_t *) b;
    return x < y ? -1 : x > y;
}

static uint64_t ref_count(const Ref *r, IsamKey lo, IsamKey hi)
{
    uint64_t c = 0;
    for (uint64_t i = 0; i < r->n; i++)
        if (r->a[i].key >= lo && r->a[i].key <= hi)
            c++;
    return c;
}

static void verify_eq(IsamFile *f, const Ref *r, IsamKey k)
{
    static IsamEntry *out;
    static const size_t cap = 200000;
    size_t found = 0;
    uint64_t exp = ref_count(r, k, k);

    if (!out)
        out = malloc(cap * sizeof(IsamEntry));
    CHECK(isam_search_eq(f, k, out, cap, &found) == ISAM_OK);
    CHECK(found == exp);
    if (found != exp || found > cap)
        return;

    uint32_t *want = malloc((exp ? exp : 1) * sizeof(uint32_t));
    uint32_t *got = malloc((exp ? exp : 1) * sizeof(uint32_t));
    uint64_t w = 0;
    for (uint64_t i = 0; i < r->n; i++)
        if (r->a[i].key == k)
            want[w++] = r->a[i].tid_blk;
    for (uint64_t i = 0; i < found; i++)
        got[i] = out[i].tid_blk;
    qsort(want, w, sizeof(uint32_t), cmp_u32);
    qsort(got, found, sizeof(uint32_t), cmp_u32);
    CHECK(memcmp(want, got, w * sizeof(uint32_t)) == 0);
    free(want);
    free(got);
}

static void verify_range(IsamFile *f, const Ref *r, IsamKey lo, IsamKey hi)
{
    uint64_t c = 0;
    CHECK(isam_search_range_count(f, lo, hi, &c) == ISAM_OK);
    CHECK(c == ref_count(r, lo, hi));
}

static void verify_all(IsamFile *f, const Ref *r, IsamKey min, IsamKey max, int nq)
{
    int64_t span = (int64_t) max - (int64_t) min + 20;
    for (int t = 0; t < nq; t++) {
        IsamKey a = (IsamKey) (min - 10 + (int64_t) (rnd() % (uint64_t) span));
        IsamKey b = (IsamKey) (min - 10 + (int64_t) (rnd() % (uint64_t) span));
        verify_eq(f, r, a);
        verify_range(f, r, a < b ? a : b, a < b ? b : a);
    }
    verify_range(f, r, INT32_MIN, INT32_MAX);
    verify_range(f, r, INT32_MIN, INT32_MIN);
    verify_range(f, r, INT32_MAX, INT32_MAX);
}

static void insert_key(IsamFile *f, Ref *r, IsamKey k)
{
    IsamEntry e = mk(k, (uint32_t) (10000000 + r->n));
    CHECK(isam_insert(f, e) == ISAM_OK);
    r->a[r->n++] = e;
}

static void build_ref(IsamFile *f, const char *path, Ref *r, uint64_t n, int64_t step, uint32_t fill, uint64_t extra)
{
    IsamEntry *a = malloc((n ? n : 1) * sizeof(IsamEntry));
    for (uint64_t i = 0; i < n; i++)
        a[i] = mk((IsamKey) ((int64_t) i * step), (uint32_t) i);
    CHECK(isam_build(f, path, a, n, fill) == ISAM_OK);
    *r = ref_new(n + extra + 4);
    memcpy(r->a, a, n * sizeof(IsamEntry));
    r->n = n;
    free(a);
}

static void test_empty(void)
{
    printf("[1] insertar en un indice vacio (3000 claves con duplicados)\n");
    IsamFile f;
    Ref r;
    build_ref(&f, "/tmp/t_i_empty.isam", &r, 0, 1, 0, 3000);
    for (int i = 0; i < 3000; i++)
        insert_key(&f, &r, (IsamKey) (rnd() % 1001) - 500);
    CHECK(f.meta.n_keys == 3000);
    CHECK(f.meta.n_overflow_blocks >= 1);
    verify_all(&f, &r, -500, 500, 150);
    isam_close(&f);
    unlink("/tmp/t_i_empty.isam");
    free(r.a);
}

static void test_with_room(void)
{
    printf("[2] relleno al 50%%: las inserciones caben sin overflow\n");
    IsamFile f;
    Ref r;
    build_ref(&f, "/tmp/t_i_room.isam", &r, 10000, 10, 50, 3000);
    for (int i = 0; i < 3000; i++)
        insert_key(&f, &r, (IsamKey) (rnd() % 100000));
    CHECK(f.meta.n_overflow_blocks == 0);
    verify_all(&f, &r, 0, 100000, 150);
    isam_close(&f);
    unlink("/tmp/t_i_room.isam");
    free(r.a);
}

static void test_uniform_overflow(void)
{
    printf("[3] relleno al 100%%: overflow uniforme, extremos int32 y claves fuera de rango\n");
    IsamFile f;
    Ref r;
    build_ref(&f, "/tmp/t_i_uni.isam", &r, 20000, 10, 100, 5200);
    for (int i = 0; i < 5000; i++)
        insert_key(&f, &r, (IsamKey) (rnd() % 220000) - 10000);
    insert_key(&f, &r, INT32_MIN);
    insert_key(&f, &r, INT32_MAX);
    insert_key(&f, &r, -1);
    insert_key(&f, &r, 200000);
    CHECK(f.meta.n_overflow_blocks > 0);
    verify_all(&f, &r, -10000, 210000, 200);
    verify_eq(&f, &r, INT32_MIN);
    verify_eq(&f, &r, INT32_MAX);
    isam_close(&f);
    unlink("/tmp/t_i_uni.isam");
    free(r.a);
}

static void test_skewed(void)
{
    printf("[4] carga sesgada (D3): 50k inserciones en 100 claves, estadisticas y reorganizacion\n");
    const char *path = "/tmp/t_i_skew.isam";
    IsamFile f;
    Ref r;
    IsamStats st;
    IsamEntry out[8];
    size_t found;

    build_ref(&f, path, &r, 100000, 1, 80, 50000);
    for (int i = 0; i < 50000; i++)
        insert_key(&f, &r, 50000 + (IsamKey) (rnd() % 100));

    CHECK(isam_stats(&f, &st) == ISAM_OK);
    printf("    bloques DATA=%u, overflow=%u, bloques con cadena=%u, cadena maxima=%u\n",
           st.data_blocks, st.overflow_blocks, st.chained_blocks, st.longest_chain);
    CHECK(st.n_keys == 150000);
    CHECK(st.longest_chain >= 20);
    CHECK(st.chained_blocks <= 3);
    CHECK(isam_needs_reorg(&f, 25));
    CHECK(!isam_needs_reorg(&f, 90));

    verify_all(&f, &r, 49900, 50200, 60);
    verify_all(&f, &r, 0, 100000, 40);

    f.n_reads = 0;
    CHECK(isam_search_eq(&f, 10, out, 8, &found) == ISAM_OK && found == 1);
    uint64_t cold = f.n_reads;
    f.n_reads = 0;
    CHECK(isam_search_eq(&f, 50010, out, 8, &found) == ISAM_OK);
    uint64_t hot = f.n_reads;
    printf("    lecturas: clave fria=%llu, clave caliente=%llu\n",
           (unsigned long long) cold, (unsigned long long) hot);
    CHECK(hot > cold * 5);

    CHECK(isam_reorganize(&f, path) == ISAM_OK);
    CHECK(isam_stats(&f, &st) == ISAM_OK);
    printf("    tras reorganizar: DATA=%u, overflow=%u, cadena maxima=%u\n",
           st.data_blocks, st.overflow_blocks, st.longest_chain);
    CHECK(st.n_keys == 150000 && st.overflow_blocks == 0 && st.longest_chain == 0);
    CHECK(!isam_needs_reorg(&f, 25));
    verify_all(&f, &r, 49900, 50200, 60);
    verify_all(&f, &r, 0, 100000, 40);

    f.n_reads = 0;
    CHECK(isam_search_eq(&f, 50010, out, 8, &found) == ISAM_OK);
    printf("    lecturas clave caliente tras reorganizar=%llu\n", (unsigned long long) f.n_reads);
    CHECK(f.n_reads * 4 < hot);
    isam_close(&f);
    unlink(path);
    free(r.a);
}

static void test_persistence(void)
{
    printf("[5] persistencia tras cerrar/reabrir y archivo de solo lectura\n");
    const char *path = "/tmp/t_i_pers.isam";
    IsamFile f;
    Ref r;
    IsamStats st;
    uint32_t ov;

    build_ref(&f, path, &r, 5000, 2, 100, 2000);
    for (int i = 0; i < 2000; i++)
        insert_key(&f, &r, 4000 + (IsamKey) (rnd() % 50));
    ov = f.meta.n_overflow_blocks;
    CHECK(ov > 0);
    CHECK(isam_close(&f) == ISAM_OK);

    CHECK(isam_open(&f, path, 0) == ISAM_OK);
    CHECK(f.meta.n_keys == 7000 && f.meta.n_overflow_blocks == ov);
    CHECK(isam_stats(&f, &st) == ISAM_OK && st.n_keys == 7000);
    verify_all(&f, &r, 0, 10000, 80);
    CHECK(isam_insert(&f, mk(1, 1)) == ISAM_ERR_IO);
    isam_close(&f);

    CHECK(isam_open(&f, path, 1) == ISAM_OK);
    insert_key(&f, &r, 4010);
    CHECK(isam_close(&f) == ISAM_OK);
    CHECK(isam_open(&f, path, 0) == ISAM_OK && f.meta.n_keys == 7001);
    verify_eq(&f, &r, 4010);
    isam_close(&f);
    unlink(path);
    free(r.a);
}

static int dead_mod3(const IsamEntry *e, void *arg)
{
    (void) arg;
    return e->tid_blk % 3 == 0;
}

static int dead_all(const IsamEntry *e, void *arg)
{
    (void) e;
    (void) arg;
    return 1;
}

static void test_delete(void)
{
    printf("[6] isam_delete_if: borrado masivo con overflow, reinsercion y borrado total\n");
    const char *path = "/tmp/t_i_del.isam";
    IsamFile f;
    Ref r;
    uint64_t removed = 0, remaining = 0, exp_removed = 0, keep = 0;

    build_ref(&f, path, &r, 20000, 5, 100, 6000);
    for (int i = 0; i < 5000; i++)
        insert_key(&f, &r, (IsamKey) (rnd() % 110000) - 5000);
    CHECK(f.meta.n_overflow_blocks > 0);

    for (uint64_t i = 0; i < r.n; i++) {
        if (r.a[i].tid_blk % 3 == 0)
            exp_removed++;
        else
            r.a[keep++] = r.a[i];
    }
    r.n = keep;
    CHECK(isam_delete_if(&f, dead_mod3, NULL, &removed, &remaining) == ISAM_OK);
    CHECK(removed == exp_removed && remaining == r.n && f.meta.n_keys == r.n);
    verify_all(&f, &r, -5000, 105000, 150);

    for (int i = 0; i < 500; i++)
        insert_key(&f, &r, (IsamKey) (rnd() % 110000) - 5000);
    verify_all(&f, &r, -5000, 105000, 100);

    CHECK(isam_close(&f) == ISAM_OK);
    CHECK(isam_open(&f, path, 1) == ISAM_OK && f.meta.n_keys == r.n);
    verify_all(&f, &r, -5000, 105000, 40);

    CHECK(isam_delete_if(&f, dead_all, NULL, &removed, &remaining) == ISAM_OK);
    CHECK(remaining == 0 && removed == r.n);
    r.n = 0;
    verify_all(&f, &r, -5000, 105000, 20);
    insert_key(&f, &r, 42);
    verify_eq(&f, &r, 42);
    isam_close(&f);
    unlink(path);
    free(r.a);
}

static void test_tail_pointer(void)
{
    printf("[7] puntero a la cola del overflow: costo O(1) y compatibilidad con cadenas sin puntero\n");
    const char *path = "/tmp/t_i_tail.isam";
    IsamFile f;
    Ref r;
    IsamStats st;
    IsamBlock b;
    IsamBlockNo prim;

    build_ref(&f, path, &r, 100000, 1, 80, 60000);
    f.n_reads = 0;
    for (int i = 0; i < 40000; i++)
        insert_key(&f, &r, 50000 + (IsamKey) (rnd() % 100));
    CHECK(f.n_reads < 40000ull * 4);
    CHECK(isam_stats(&f, &st) == ISAM_OK);
    CHECK(st.longest_chain >= 20);
    CHECK(st.n_keys == r.n);

    CHECK(isam_index_descend(&f, 50010, ISAM_DESCEND_UPPER, &prim) == ISAM_OK);
    CHECK(isam_read_block(&f, prim, &b) == ISAM_OK);
    CHECK(isam_hdr(&b)->level != 0 && isam_hdr(&b)->overflow_next != ISAM_INVALID_BLOCK);
    isam_hdr(&b)->level = 0;
    CHECK(isam_write_block(&f, prim, &b) == ISAM_OK);

    uint32_t chain_before = st.longest_chain;
    for (int i = 0; i < 3000; i++)
        insert_key(&f, &r, 50000 + (IsamKey) (rnd() % 100));
    CHECK(isam_read_block(&f, prim, &b) == ISAM_OK);
    CHECK(isam_hdr(&b)->level != 0);
    CHECK(isam_stats(&f, &st) == ISAM_OK);
    CHECK(st.longest_chain >= chain_before);
    CHECK(st.n_keys == r.n);
    verify_all(&f, &r, 49900, 50200, 80);
    verify_all(&f, &r, 0, 100000, 30);

    CHECK(isam_close(&f) == ISAM_OK);
    unlink(path);
    free(r.a);
}

int main(void)
{
    test_empty();
    test_with_room();
    test_uniform_overflow();
    test_skewed();
    test_persistence();
    test_delete();
    test_tail_pointer();
    printf("\n%d verificaciones, %d fallos\n", checks, fails);
    return fails ? 1 : 0;
}
