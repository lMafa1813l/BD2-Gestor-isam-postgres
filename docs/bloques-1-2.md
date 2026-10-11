# Bloques 1 y 2 — Docker/hello world AM e ISAM puro en C

## Bloque 1: entorno y "hello world" AM
- `docker/Dockerfile`: imagen `postgres:${PG_VERSION}` (por defecto 18) + `build-essential` + `postgresql-server-dev`. Compila e instala `isam_am` al construir la imagen.
- `docker/docker-compose.yml`: contenedor `isam_pg`, puerto host **5433**, BD `bd2`.
- `isam_am/`: `isam_handler.c` (IndexAmRoutine con callbacks mínimos), `isam_am.control`, `isam_am--1.0.sql` (`CREATE ACCESS METHOD isam_am` + operator class `int4_ops`), `Makefile` PGXS.
- Prueba (Bloque 1, ya reemplazada): el "hello world" se verificó con `make hello`. Desde el Bloque 4 la prueba equivalente es `make integration`.
- Para fijar la versión exacta: `PG_VERSION=18.x docker compose -f docker/docker-compose.yml up -d --build` (usar una etiqueta que exista en Docker Hub).

## Bloque 2: núcleo ISAM en C (`isam_am/core/`)
| Archivo | Contenido |
|---|---|
| `isam_layout.h` | Formato de bloque de 8192 B: cabecera 16 B, DATA (681 entradas de 12 B), INDEX (1022 entradas de 8 B), META |
| `isam_io.[ch]` | Lectura/escritura por bloque, contadores `n_reads`/`n_writes`, `isam_alloc_block` (para overflow) |
| `isam_index.[ch]` | `isam_build` (O(N), índice de niveles bottom-up), `isam_index_descend` (búsqueda binaria por nivel) |
| `isam_search.[ch]` | Iterador de rango, `isam_search_eq`, recorrido de cadena de overflow |

Archivo: `[META][DATA 1..D][INDEX nivel 1 ... raíz][OVERFLOW ...]`.

Decisiones de diseño
- Claves repetidas permitidas. Las búsquedas descienden con "último separador < clave" (`ISAM_DESCEND_LOWER`) y siguen hacia adelante; la inserción (Bloque 3) usará "último separador <= clave" (`ISAM_DESCEND_UPPER`).
- Costo de un lookup = niveles de índice + 1 bloque DATA (+ cadena de overflow). Con 1,000,000 claves y llenado 100%: 1469 bloques DATA, 2 niveles, **3 lecturas**.
- Invariante que usa el escaneo y que debe respetar la inserción del Bloque 3: toda entrada de un bloque (y de su overflow) es >= su separador; así un rango se corta al ver un bloque cuya primera clave ya supera el límite superior.
- Las entradas de overflow no están ordenadas; el índice no es `amcanorder`.
- Enteros en orden de bytes nativo.

## Pruebas
`make test` compila `tests/test_isam_core.c` con `-Wall -Wextra -Wpedantic` y corre 3774 verificaciones: índice vacío, igualdad presentes/ausentes, factor de llenado, entrada desordenada, duplicados que cruzan bloques, 700 consultas aleatorias contra una referencia por fuerza bruta (con INT32_MIN/MAX), 1M de claves y overflow armado a mano.
