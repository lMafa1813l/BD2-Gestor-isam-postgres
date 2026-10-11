# BD2 - ISAM como Access Method en PostgreSQL

Proyecto del curso Base de Datos 2 (Grupo 9).

## Integrantes

1. Medina Grados, Fabian Esteban
2. Vargas Llerena, Bryan Aron
3. Villanueva Valencia, Andy Jeferson
4. Chavez Quijahuaman, Jorge
5. Becerra Reymer, Leonardo Sebastian

## Estructura

| Carpeta | Contenido |
|---|---|
| `isam_am/` | Extensión en C: Access Method ISAM para PostgreSQL 18.6 |
| `datasets/` | Generadores de datasets D1/D2/D3 |
| `workloads/` | Scripts de workload W1-W4 |
| `benchmarks/` | Benchmarks: sin índice vs B-tree vs ISAM |
| `docker/` | Entorno reproducible |
| `tests/` | Pruebas unitarias e integración |
| `docs/` | Informe y documentación de diseño |
| `legacy/` | Simulador de disco en Python con AVL (versión previa, solo referencia) |

## Cómo probar
| Comando | Qué hace |
|---|---|
| `make test` | Pruebas del núcleo ISAM en C (solo requiere `gcc` y `make`) |
| `make integration` | Bloque 4: levanta PostgreSQL 18 en Docker y corre las pruebas end-to-end del AM (`tests/sql/isam_integration.sql`) |
| `make bench` | Bloque 5: benchmark sin índice vs B-tree vs ISAM sobre D1/D2/D3 y W1-W4; deja un CSV en `benchmarks/results/` (ej. `N=1000000 T=20 make bench`) |
| `make overflow` | Bloque 6: experimento de overflow bajo inserciones sesgadas (`INSERT_MODE=narrow DATASET=d1 make overflow`) |
| `make crash-load` | Bloque 6: mata el servidor en plena carga concurrente de inserts y verifica el índice |
| `make report` | Bloque 6: resumen Markdown y gráficos PNG del último CSV de `benchmarks/results/` (requiere Python 3; los gráficos, matplotlib) |
| `make crash` | Bloque 4: simula una caída del servidor y verifica la recuperación (WAL del índice y tablas UNLOGGED) |

Detalles en [`docs/bloques-1-2.md`](docs/bloques-1-2.md) y [`docs/bloque-3.md`](docs/bloque-3.md) [`docs/bloque-4.md`](docs/bloque-4.md) [`docs/bloque-5.md`](docs/bloque-5.md) y [`docs/bloque-6.md`](docs/bloque-6.md) y [`docs/analisis-resultados-18.6.md`](docs/analisis-resultados-18.6.md).

## Uso rápido del índice
```sql
CREATE EXTENSION isam_am;
SET isam_am.fill_pct = 80;
CREATE INDEX idx ON tabla USING isam_am (columna_int4);

SELECT * FROM isam_index_stats('idx');
SELECT isam_reorg_needed('idx', 25);
REINDEX INDEX idx;
```
