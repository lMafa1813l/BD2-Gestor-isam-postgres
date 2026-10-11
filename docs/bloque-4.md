# Bloque 4: integración con PostgreSQL

El núcleo ISAM (`isam_am/core/`) ahora vive dentro de las páginas de PostgreSQL y el Access Method (`isam_am/*.c`) ya no es un "hello world".

## Qué cambió en el núcleo
| Cambio | Detalle |
|---|---|
| Layout dentro de la página PG | `ISAM_BODY_OFFSET` = 0 en modo standalone y `SizeOfPageHeaderData` (24) con `-DISAM_IN_POSTGRES`. Capacidades: DATA 679 y INDEX 1019 en PG (681 y 1022 standalone). |
| `pd_lower`/`pd_upper` | Se fijan en `BLCKSZ` para que el WAL no descarte ningún byte como "hueco" de página. |
| E/S separada | `isam_io.c` (común), `isam_io_file.c` (tests, `pread/pwrite`), `isam_io_pg.c` (buffer manager + GenericXLog). |
| Construcción | `isam_build_sorted()` no crea archivos; `isam_build()` (archivo) la envuelve. `isam_make_empty()` genera un ISAM vacío para `ambuildempty`. |
| Borrado | `isam_delete_if()` compacta bloques primarios y de overflow; la usa `ambulkdelete`. |
| Memoria | `ISAM_MALLOC/ISAM_FREE` (`palloc/pfree` en PG). |

## Callbacks del Access Method
| Archivo | Callback | Comportamiento |
|---|---|---|
| `isam_am_build.c` | `ambuild` | Lee el heap con `table_index_build_scan`, ignora NULL, ordena y llama a `isam_build_sorted` con `isam_am.fill_pct`. |
| | `ambuildempty` | Escribe META + un DATA vacío en el fork INIT (tablas UNLOGGED) con `log_newpage_buffer`. |
| `isam_am_insert.c` | `aminsert` | Ignora NULL. Serializa con `LockRelationForExtension`, relee el META y llama a `isam_insert`. |
| `isam_am_scan.c` | `ambeginscan`/`amrescan`/`amgettuple`/`amgetbitmap`/`amendscan` | Traduce las scan keys (estrategias 1 a 5) a límites inferior/superior, tomando el más estricto. Solo recorrido hacia adelante. `xs_recheck = false`. |
| `isam_am_vacuum.c` | `ambulkdelete` | Elimina del índice las entradas cuyo TID declara muerto VACUUM. |
| | `amvacuumcleanup` | Actualiza `num_pages`. |
| `isam_am_cost.c` | `amcostestimate` | `genericcostestimate` de PostgreSQL. El planner elige ISAM sin forzarlo. |
| `isam_handler.c` | handler, `_PG_init` | Registra la GUC `isam_am.fill_pct` (10 a 100, defecto 80) y rechaza `WITH (...)`. |

## WAL y concurrencia
- **WAL:** cada escritura de bloque usa `GenericXLog`: imagen completa solo para páginas recién creadas y registros delta (solo los bytes que cambian) para las existentes (ver `docs/bloque-6.md`). Es físico y sirve para recuperación y réplicas físicas; sigue siendo más voluminoso que el WAL de un B-tree.
- **Inserciones:** una a la vez por índice (bloqueo de extensión de la relación). Los scans leen cada página bajo bloqueo compartido de buffer y nunca ven una página a medias.
- **VACUUM:** toma el mismo bloqueo, así que bloquea inserciones mientras compacta.

## Limitaciones conocidas (documentar en el informe)
1. Solo clave `int4` de una columna; sin unicidad, sin `ORDER BY` por índice, sin recorrido hacia atrás, sin index-only scan.
2. El índice es estático: los separadores no cambian tras construir. La carga sesgada degrada la búsqueda (cadenas de overflow largas). La cura es `REINDEX`, que reconstruye desde el heap.
4. Un insert serializa con los demás inserts del mismo índice.
6. `n_keys` del META es aproximado tras inserciones; `isam_index_stats()` (Bloque 6) cuenta las entradas reales.
5. `CREATE INDEX CONCURRENTLY` y construcción paralela no están soportados ni probados.

## Pruebas
| Comando | Qué valida |
|---|---|
| `make test` | Núcleo en C: 3774 + 74 081 verificaciones, sin errores con AddressSanitizer/UBSan. |
| `make integration` | `tests/sql/isam_integration.sql`: 100k enteros (duplicados, negativos, INT_MIN/INT_MAX, NULL); 21 consultas de igualdad y rango comparadas contra seqscan tras: build, inserts uniformes y sesgados con overflow, UPDATE/DELETE, VACUUM, VACUUM FULL, REINDEX, `fill_pct = 100`, tabla UNLOGGED, tabla TEMP e índice creado sobre tabla vacía. Verifica que el plan use el índice y que el planner lo elija solo en igualdad. |
| `make crash` | `crash_1.sql` y `crash_2.sql`: tras `docker kill`, el índice se reconstruye por WAL y coincide con seqscan; la tabla UNLOGGED queda vacía con índice válido. |

## Estado de verificación
- Probado en PostgreSQL **16.15**: compilación sin warnings, `make integration` completo, recuperación tras caída y una prueba de concurrencia con `pgbench` (8 clientes con inserts, selects y deletes simultáneos; 0 errores; el índice coincide con seqscan).
- PostgreSQL **18.6**: pendiente de ejecutar `make integration` y `make crash` en Docker. Las APIs usadas (`ExtendBufferedRel`, `GenericXLog`, `genericcostestimate`, `log_newpage_buffer`) existen en 16, 17 y 18.
