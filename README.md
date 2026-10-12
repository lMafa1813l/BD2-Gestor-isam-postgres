# BD2 - ISAM como Access Method en PostgreSQL

**Entrega revisada, bloques 0–6:** PostgreSQL 18.6 fijado, regresión
DELETE/VACUUM corregida y benchmarks con cuotas fijas, semillas y cinco
reconstrucciones independientes. La propuesta original se conserva en
[`docs/propuesta-inicial.pdf`](docs/propuesta-inicial.pdf).

## Requisitos y arranque desde cero

Linux, Docker Engine/Compose v2, Python 3, `gcc`, `make` y `flock`. Desde este
checkout, que debe incluir las correcciones de la entrega:

```bash
make test
make integration
make demo
```

La compilación fija la imagen PostgreSQL 18.6 por digest y construye servidor y
PGXS desde el mismo commit oficial, con checksum. Usa paquetes Debian firmados,
HTTPS y, cuando existe, la CA/proxy proporcionada por el entorno. No depende de
`apt.postgresql.org`. La configuración de este servidor académico no incluye
ICU, readline ni zlib. El servicio escucha solo en 127.0.0.1:5433; credenciales
locales de desarrollo: usuario y contraseña `postgres`, base `bd2`.

`make integration` valida 210 comparaciones y ejecuta el caso de VACUUM por
Index Scan/Bitmap Scan. Para arrancar sin ejecutar las pruebas:

```bash
bash docker/start.sh
docker exec -it isam_pg psql -X -U postgres -d bd2
```

Los scripts adquieren un bloqueo por contenedor: no se puede ejecutar una prueba
de caída o demo mientras un benchmark lo utiliza. No borrar el volumen para
actualizar una imagen. Para un entorno nuevo sin tocar el existente, usar
`COMPOSE_PROJECT_NAME=isam_defensa ISAM_CONTAINER_NAME=isam_defensa_pg ISAM_PORT=5434`
con los mismos targets. Más pasos y preguntas: [`docs/defensa.md`](docs/defensa.md).

## Experimentos corregidos

```bash
make bench        # D1/D2/D3 × 100k/500k/1M × none/btree/isam × 5 replicas
make overflow     # D1 narrow, N=100k, 5 trayectorias por configuración
make crash
make crash-load
```

El barrido completo consume tiempo: incluye 135 cargas independientes y 90
construcciones de índices, con acceso sin índice a las tres escalas. Cada réplica
ejecuta W1=10 000 búsquedas presentes, W2=10 000 ausentes, W3=N/10 inserciones,
W4=1 000 rangos y las lecturas posteriores. Se permite duplicación de claves en
W3; las tablas iniciales son únicas. Las filas iniciales/finales, cuotas, fallos,
semillas y huellas de inserción se verifican. D1 se carga en orden; D2 permuta
1..N con semilla 0.42; D3 usa esos mismos datos y consultas Zipf 1.1.

Cada CSV tiene metadatos `.json` y logs. Solo `status=completed` valida la corrida.
Las corridas `BENCH_SMOKE=1` son diagnósticos y no resultados oficiales:

```bash
BENCH_SMOKE=1 N=2000 REPS=1 EQ_QUERIES=100 RANGE_QUERIES=20 make bench
BENCH_SMOKE=1 N=2000 REPS=1 BATCHES=1 HOT_QUERIES=20 make overflow
```

Los runners también funcionan fuera de Docker definiendo `PSQL`, `PGBENCH`,
`PGB_DB`, `WORKLOADS` y, si la ruta de los SQL difiere, `DATASETS_DIR`. Docker usa
bases separadas: `isam_benchmark` y `isam_overflow`.

## Informe y evidencia

La entrega conserva los CSV/metadatos corregidos en `docs/results/` y el informe
completo en [`report.tex`](report.tex). Las cifras antiguas son exploratorias y
se distinguen de las corregidas. Para regenerar tablas/figuras y PDF:

Si falta matplotlib, instalarlo en un entorno Python local:

```bash
python3 -m venv .venv-report
.venv-report/bin/pip install -r requirements-report.txt
source .venv-report/bin/activate
```

En Debian/Ubuntu, los paquetes de LaTeX utilizados son `latexmk`,
`texlive-latex-base`, `texlive-latex-recommended`, `texlive-latex-extra`,
`texlive-pictures`, `texlive-fonts-recommended` y `lmodern`. La creación del venv
puede requerir `python3-venv`. En esta máquina ya están disponibles las herramientas necesarias;
la reconstrucción Docker instala su propio compilador y cabeceras.

```bash
make report       # exige resultados completos, cuotas y hashes correctos
make pdf          # requiere TeX Live, latexmk y paquetes LaTeX estándar
```

Para incorporar una corrida nueva, elegir explícitamente los CSV completos:

```bash
python3 benchmarks/build_report.py --bench ruta/bench.csv --overflow ruta/overflow.csv
make pdf
```

Se reporta mediana e IQR de cinco réplicas; la latencia de cada réplica es la
media informada por pgbench. No se infieren percentiles de latencia por consulta
a partir de esos promedios. Los bloques distribuidos 7–8 quedan pendientes.
La declaración de recursos y asistencia de IA está en el informe y la guía.
El informe y la guía de defensa están disponibles también en la raíz del repositorio.

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
| `make bench` | Bloque 5: tres tamaños, D1/D2/D3, cuotas W1-W4 y cinco repeticiones independientes; CSV, metadatos y logs en `benchmarks/results/` |
| `make overflow` | Bloque 6: experimento de overflow bajo inserciones sesgadas (`INSERT_MODE=narrow DATASET=d1 make overflow`) |
| `make crash-load` | Bloque 6: mata el servidor en plena carga concurrente de inserts y verifica el índice |
| `make report` | Bloque 6: valida los CSV corregidos de `docs/results/` y genera tablas LaTeX y figuras PDF (requiere Python 3 y matplotlib) |
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
