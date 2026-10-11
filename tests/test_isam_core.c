/* Pruebas del núcleo ISAM puro (Bloque 2). Sin PostgreSQL. */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include "isam_core.h"

static int fails = 0, checks = 0;
#define CHECK(c) do { checks++; if (!(c)) { fails++; printf("  FALLO %s:%d: %s\n", __FILE__, __LINE__, #c); } } while (0)

static uint64_t rng_s = 88172645463325252ull;
static uint64_t rnd(void) { rng_s ^= rng_s << 13; rng_s ^= rng_s >> 7; rng_s ^= rng_s << 17; return rng_s; }

static IsamEntry mk(IsamKey k, uint32_t i) { IsamEntry e = { k, i, (uint16_t)(i % 100 + 1), 0 }; return e; }

static uint64_t ref_range(const IsamEntry *a, uint64_t n, const IsamBound *lo, const IsamBound *hi)
{
    uint64_t c = 0;
    for (uint64_t i = 0; i < n; i++) {
        IsamKey k = a[i].key;
        if (lo->present && (k < lo->key || (k == lo->key && !lo->inclusive))) continue;
        if (hi->present && (k > hi->key || (k == hi->key && !hi->inclusive))) continue;
        c++;
    }
    return c;
}

static uint64_t scan_count(IsamFile *f, IsamBound lo, IsamBound hi)
{
    IsamScan s; IsamEntry e; uint64_t n = 0;
    if (isam_scan_begin(&s, f, lo, hi) != ISAM_OK) return (uint64_t)-1;
    while (isam_scan_next(&s, &e) == 1) n++;
    return n;
}

static void test_empty(void)
{
    printf("[1] indice vacio\n");
    IsamFile f; size_t found = 99;
    CHECK(isam_build(&f, "/tmp/t_empty.isam", NULL, 0, 0) == ISAM_OK);
    CHECK(f.meta.n_data_blocks == 1 && f.meta.n_index_levels == 0 && f.meta.n_blocks == 2);
    CHECK(isam_search_eq(&f, 5, NULL, 0, &found) == ISAM_OK && found == 0);
    isam_close(&f); unlink("/tmp/t_empty.isam");
}

static void test_basic(void)
{
    printf("[2] construccion y busqueda basica (claves pares 0..1998)\n");
    enum { N = 1000 };
    IsamEntry a[N]; IsamFile f; IsamEntry out[4]; size_t found;
    for (int i = 0; i < N; i++) a[i] = mk(i * 2, i);
    CHECK(isam_build(&f, "/tmp/t_basic.isam", a, N, 100) == ISAM_OK);
    CHECK(f.meta.n_data_blocks == 2);                     /* ceil(1000/681) */
    CHECK(f.meta.n_index_levels == 1 && f.meta.root_block == 3);
    CHECK(f.meta.n_blocks == 4);
    for (int i = 0; i < N; i++) {
        CHECK(isam_search_eq(&f, i * 2, out, 4, &found) == ISAM_OK && found == 1);
        CHECK(out[0].tid_blk == (uint32_t) i);
    }
    for (int i = -3; i < 2003; i += 2) {                  /* impares: ausentes */
        CHECK(isam_search_eq(&f, i, out, 4, &found) == ISAM_OK && found == 0);
    }
    /* costo de E/S de un lookup: altura = niveles de indice + 1 bloque DATA */
    f.n_reads = 0;
    isam_search_eq(&f, 1000, out, 4, &found);
    CHECK(f.n_reads == f.meta.n_index_levels + 1);
    /* reabrir el archivo */
    isam_close(&f);
    CHECK(isam_open(&f, "/tmp/t_basic.isam", 0) == ISAM_OK);
    CHECK(f.meta.n_keys == N && f.meta.root_block == 3);
    CHECK(isam_search_eq(&f, 1998, out, 4, &found) == ISAM_OK && found == 1);
    isam_close(&f); unlink("/tmp/t_basic.isam");
}

static void test_fill(void)
{
    printf("[3] factor de llenado\n");
    enum { N = 6810 };
    IsamEntry *a = malloc(N * sizeof *a); IsamFile f;
    for (int i = 0; i < N; i++) a[i] = mk(i, i);
    isam_build(&f, "/tmp/t_fill.isam", a, N, 100); CHECK(f.meta.n_data_blocks == 10); isam_close(&f);
    isam_build(&f, "/tmp/t_fill.isam", a, N, 50);  CHECK(f.meta.n_data_blocks == 21); /* 340 por bloque: ceil(6810/340) */
    size_t found; CHECK(isam_search_eq(&f, 6809, NULL, 0, &found) == ISAM_OK && found == 1);
    isam_close(&f); unlink("/tmp/t_fill.isam"); free(a);
}

static void test_unsorted(void)
{
    printf("[4] entrada desordenada se rechaza\n");
    IsamEntry a[3] = { mk(1,0), mk(5,1), mk(3,2) }; IsamFile f;
    CHECK(isam_build(&f, "/tmp/t_uns.isam", a, 3, 0) == ISAM_ERR_UNSORTED);
    CHECK(isam_build(&f, "/tmp/t_uns.isam", a, 3, 5) == ISAM_ERR_ARG);
    unlink("/tmp/t_uns.isam");
}

static void test_duplicates(void)
{
    printf("[5] duplicados que cruzan bloques (cada clave x1500)\n");
    enum { K = 20, R = 1500, N = K * R };
    IsamEntry *a = malloc(N * sizeof *a); IsamFile f; size_t found;
    for (int k = 0; k < K; k++) for (int r = 0; r < R; r++) a[k * R + r] = mk(k * 10, k * R + r);
    CHECK(isam_build(&f, "/tmp/t_dup.isam", a, N, 100) == ISAM_OK);
    for (int k = 0; k < K; k++) {
        CHECK(isam_search_eq(&f, k * 10, NULL, 0, &found) == ISAM_OK && found == R);
        CHECK(isam_search_eq(&f, k * 10 + 1, NULL, 0, &found) == ISAM_OK && found == 0);
    }
    isam_close(&f); unlink("/tmp/t_dup.isam"); free(a);
}

static void test_range_random(void)
{
    printf("[6] rangos aleatorios vs. referencia (200k claves, con extremos int32)\n");
    enum { N = 200000 };
    IsamEntry *a = malloc(N * sizeof *a); IsamFile f;
    for (int i = 0; i < N; i++) a[i] = mk((IsamKey)(rnd() % 100000) - 50000, i);
    a[0].key = INT32_MIN; a[1].key = INT32_MAX; a[2].key = INT32_MIN;
    isam_sort_entries(a, N);
    CHECK(isam_build(&f, "/tmp/t_rng.isam", a, N, 0) == ISAM_OK);
    printf("    bloques DATA=%u, niveles de indice=%u, total bloques=%u\n",
           f.meta.n_data_blocks, f.meta.n_index_levels, f.meta.n_blocks);
    for (int t = 0; t < 400; t++) {
        IsamBound lo = { (int)(rnd() % 5 != 0), (int)(rnd() % 2), (IsamKey)(rnd() % 110000) - 55000 };
        IsamBound hi = { (int)(rnd() % 5 != 0), (int)(rnd() % 2), (IsamKey)(rnd() % 110000) - 55000 };
        if (t == 0) { lo.present = 0; hi.present = 0; }
        if (t == 1) { lo.present = 1; lo.inclusive = 1; lo.key = INT32_MIN; hi.present = 1; hi.inclusive = 1; hi.key = INT32_MIN; }
        if (t == 2) { lo.present = 1; lo.inclusive = 1; lo.key = INT32_MAX; hi.present = 0; }
        CHECK(scan_count(&f, lo, hi) == ref_range(a, N, &lo, &hi));
    }
    for (int t = 0; t < 300; t++) {                       /* igualdad */
        IsamKey k = (IsamKey)(rnd() % 100000) - 50000; size_t found;
        IsamBound b = { 1, 1, k };
        CHECK(isam_search_eq(&f, k, NULL, 0, &found) == ISAM_OK && found == ref_range(a, N, &b, &b));
    }
    isam_close(&f); unlink("/tmp/t_rng.isam"); free(a);
}

static void test_big_height(void)
{
    printf("[7] 1,000,000 claves: altura del indice y costo de busqueda\n");
    enum { N = 1000000 };
    IsamEntry *a = malloc((size_t)N * sizeof *a); IsamFile f;
    for (int i = 0; i < N; i++) a[i] = mk(i, i);
    CHECK(isam_build(&f, "/tmp/t_big.isam", a, N, 100) == ISAM_OK);
    printf("    DATA=%u bloques, niveles=%u, escrituras de construccion=%llu\n",
           f.meta.n_data_blocks, f.meta.n_index_levels, (unsigned long long) f.n_writes);
    CHECK(f.meta.n_data_blocks == 1469 && f.meta.n_index_levels == 2);   /* 1469 -> 2 -> 1 */
    f.n_reads = 0;
    size_t found; IsamEntry o;
    CHECK(isam_search_eq(&f, 777777, &o, 1, &found) == ISAM_OK && found == 1 && o.tid_blk == 777777);
    printf("    busqueda por igualdad = %llu lecturas de bloque\n", (unsigned long long) f.n_reads);
    CHECK(f.n_reads == 3);
    f.n_reads = 0;
    uint64_t c; CHECK(isam_search_range_count(&f, 100000, 109999, &c) == ISAM_OK && c == 10000);
    printf("    rango de 10,000 claves = %llu lecturas de bloque\n", (unsigned long long) f.n_reads);
    isam_close(&f); unlink("/tmp/t_big.isam"); free(a);
}

static void test_manual_overflow(void)
{
    printf("[8] la busqueda recorre cadenas de overflow (armadas a mano)\n");
    enum { N = 2000 };
    IsamEntry a[N]; IsamFile f; IsamBlockNo ov1, ov2; IsamBlock b; size_t found;
    for (int i = 0; i < N; i++) a[i] = mk(i * 10, i);
    CHECK(isam_build(&f, "/tmp/t_ov.isam", a, N, 100) == ISAM_OK);   /* 3 bloques DATA */
    CHECK(isam_alloc_block(&f, ISAM_BLK_OVERFLOW, 0, &ov1) == ISAM_OK);
    CHECK(isam_alloc_block(&f, ISAM_BLK_OVERFLOW, 0, &ov2) == ISAM_OK);
    /* bloque DATA 2 cubre claves 6810..13619; cadena con claves 6815 y 6817 (ov1) y 6815 (ov2) */
    IsamBlockNo primary = 2;
    isam_read_block(&f, ov1, &b);
    isam_entries(&b)[0] = mk(6815, 5000); isam_entries(&b)[1] = mk(6817, 5001);
    isam_hdr(&b)->nentries = 2; isam_hdr(&b)->overflow_next = ov2;
    isam_write_block(&f, ov1, &b);
    isam_read_block(&f, ov2, &b);
    isam_entries(&b)[0] = mk(6815, 5002); isam_hdr(&b)->nentries = 1;
    isam_write_block(&f, ov2, &b);
    isam_read_block(&f, primary, &b);
    isam_hdr(&b)->overflow_next = ov1;
    isam_write_block(&f, primary, &b);

    CHECK(isam_search_eq(&f, 6815, NULL, 0, &found) == ISAM_OK && found == 2);
    CHECK(isam_search_eq(&f, 6817, NULL, 0, &found) == ISAM_OK && found == 1);
    CHECK(isam_search_eq(&f, 6820, NULL, 0, &found) == ISAM_OK && found == 1);
    IsamBound lo = { 1, 1, 6810 }, hi = { 1, 1, 6830 };
    CHECK(scan_count(&f, lo, hi) == 3 + 3);    /* 6810,6820,6830 + 3 de overflow */
    /* un rango que termina antes del overflow no debe verlo */
    IsamBound hi2 = { 1, 1, 6810 };
    CHECK(scan_count(&f, lo, hi2) == 1);
    isam_close(&f); unlink("/tmp/t_ov.isam");
}

int main(void)
{
    test_empty(); test_basic(); test_fill(); test_unsorted();
    test_duplicates(); test_range_random(); test_big_height(); test_manual_overflow();
    printf("\n%d verificaciones, %d fallos\n", checks, fails);
    return fails ? 1 : 0;
}
