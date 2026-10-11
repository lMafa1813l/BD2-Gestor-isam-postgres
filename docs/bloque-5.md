# Bloque 5: datasets, workloads y benchmark preliminar

## Importante: definiciones asumidas
La propuesta fija que D1/D2/D3 son enteros (D3 sesgado) y que W1/W2 son igualdad y W4 rango, pero no describe cada uno al detalle. Estas son las definiciones usadas aquí. **Si la rúbrica define otras, solo hay que cambiar `datasets/*.sql` y `workloads/*.pgb`; el runner no se toca.**

| Dataset | Archivo | Distribución |
|---|---|---|
| D1 | `datasets/d1.sql` | Claves únicas 1..N en orden físico aleatorio |
| D2 | `datasets/d2.sql` | Uniforme con duplicados: dominio N/10 (unas 10 filas por clave) |
| D3 | `datasets/d3.sql` | Sesgado: 80 % de las filas en el 1 % del dominio (claves calientes, unas 80 filas por clave), resto uniforme |

Los tres usan `setseed(0.42)`: todas las configuraciones comparan exactamente los mismos datos. La tabla es `bench(id int, payload text)`.

| Workload | Archivo | Qué hace |
|---|---|---|
| W1 | `w1_eq_uniform.pgb` | Igualdad con clave uniforme sobre el dominio |
| W2 | `w2_eq_absent.pgb` | Igualdad con claves **ausentes** (búsquedas no exitosas): claves en (dominio, 2·dominio], que nunca se insertan |
| W3 | `w3_insert.pgb` | Inserciones con clave uniforme |
| W5 | `w5_eq_skew.pgb` | Extra: igualdad con clave Zipf (`random_zipfian`, parámetro 1.1), accesos sesgados |
| W6 | `w6_eq_hot.pgb` | Igualdad sobre una ventana de claves calientes (la usa el experimento de overflow del Bloque 6) |
| W4 | `w4_range.pgb` | Rango `BETWEEN lo AND lo+span`, con span = dominio/1000 (0,1 % del dominio) |

Además, tras W3 el runner repite W1 y W4 (`w1_eq_after_inserts`, `w4_range_after_inserts`) para medir la degradación por overflow.

## Cómo correrlo
```
make bench
N=1000000 T=20 CLIENTS=4 make bench
DATASETS="d3" CONFIGS="btree isam" FILL=100 make bench
```
Variables: `MAINT_WORKERS` (fija `max_parallel_maintenance_workers` al construir ambos índices), `N` (filas, defecto 200000), `T` (segundos por celda, 5), `CLIENTS` (4), `REPS` (repeticiones por celda, 1), `FILL` (`isam_am.fill_pct`, 80), `DATASETS`, `CONFIGS` (`none btree isam`).
El runner (`benchmarks/run_bench.sh`) es independiente de Docker: define `PSQL`, `PGBENCH`, `PGB_DB` y `WORKLOADS` para correrlo contra cualquier PostgreSQL con `isam_am` instalada. `docker/bench.sh` los configura para el contenedor.

## Salida
CSV en `benchmarks/results/bench_<fecha>.csv` (ignorado por Git) con columnas:
`dataset, n, config, workload, rep, tps, lat_ms, build_ms, index_bytes, buffers_eq, buffers_range, overflow_blocks, longest_chain`.
- `build_ms`: tiempo de `CREATE INDEX` (con `\timing`).
- `index_bytes`: tamaño del índice **en el momento de esa fila**.
- `buffers_eq` y `buffers_range`: buffers tocados por una igualdad y un rango de muestra (`EXPLAIN (ANALYZE, BUFFERS)`), medidos en ese momento.

## Decisiones de diseño del benchmark
- **Las consultas leen `payload`** (`count(payload)`), no `count(*)`. Con `count(*)` el B-tree resuelve la consulta con *index-only scan* y ISAM (que no lo soporta) debe leer el heap; la comparación sería injusta. Así ambos leen el heap.
- La tabla se recarga antes de cada configuración, para que los inserts de W3 de una no contaminen a la siguiente.
- `VACUUM ANALYZE` antes de medir, para que el planner tenga estadísticas.

## Muestra de resultados (PostgreSQL 16 local, N = 200 000, T = 2 s: solo orientativo)
No son números finales: sirvieron para validar el harness. Tendencias observadas:
- **Lectura por igualdad:** ISAM y B-tree equivalentes (mismos buffers, throughput dentro de ±10 %).
- **Rango:** equivalentes.
- **Construcción:** ISAM más rápido (unos 55-60 ms frente a unos 100 ms en D1/D2).
- **Inserciones (W3):** ISAM entre 0 % y 40 % más lento que B-tree (WAL de página completa y un solo insertador por índice).
- **D3 tras inserts:** el overflow sube los buffers de igualdad de 3 a 4 y el tamaño del índice de 2968 KB a 3560 KB; con la carga corta usada la degradación es pequeña. Para forzarla, aumentar `T` y `N` (Bloque 6).
- **Sin índice:** unos 140 tps en igualdad frente a más de 25 000 con cualquiera de los dos índices.

## Mejora del AM encontrada gracias al benchmark
`amrescan` abría el índice y descendía por él, pero PostgreSQL lo invoca al inicializar el nodo, fuera de la medición de `EXPLAIN`. Ahora `amrescan` solo calcula los límites y el descenso ocurre en el primer `amgettuple`/`amgetbitmap` (como hace el B-tree). Es más correcto para las métricas y evita trabajo si el nodo nunca se ejecuta.

## Corrección de compatibilidad con PostgreSQL 18
`isam_am.h` declaraba `isam_am_error` con `pg_attribute_noreturn()`, macro que PostgreSQL 18 ya no define. Se eliminó (reportado y verificado en 18.6).

## Pendiente (Bloque 6)
Correr con N mayor (1M+), T largo y varias repeticiones; graficar; ajustar el umbral de overflow según D3.

## Actualización (Bloque 6)
W2 pasó a ser de claves ausentes, como pide la rúbrica; la versión Zipf quedó como W5. El orden de ejecución por configuración es W1, W2, W5, W4, W3, y luego W1 y W4 de nuevo tras las inserciones.
