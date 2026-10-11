# Análisis de los resultados en PostgreSQL 18.6

Datos: `bench_20261011_134445.csv` (N = 1 000 000, T = 20 s, REPS = 3, 4 clientes) y `overflow_20261011_133942.csv` (D3, N = 200 000, modo `dist`).

## Lectura y escritura
ISAM y B-tree rinden prácticamente igual (relación de tps ISAM/B-tree, mediana de 3 repeticiones):

| dataset | igualdad (W1/W2/W5) | rango (W4) | inserción (W3) | W1 tras inserts | W4 tras inserts |
|---|---|---|---|---|---|
| D1 | 0,96 a 0,97 | 0,99 | 0,98 | 0,99 | 1,08 |
| D2 | 0,99 a 1,02 | 1,01 | 1,03 | 1,00 | 0,99 |
| D3 | 0,96 a 1,01 | 1,00 | 0,99 | 0,95 | 0,88 |

Sin índice: 230 a 350 tps frente a 43 000 a 66 000 con cualquiera de los dos.

**No hay una caída de rendimiento atribuible a ISAM tras las inserciones.** La única diferencia apreciable es el rango de D3 tras las inserciones (0,88), donde el tps cae para ambos índices porque el rango contiene más filas (se insertaron duplicados): B-tree baja un 30 % e ISAM un 39 %.

## Tamaño del índice

| dataset | B-tree inicial → tras inserts | ISAM inicial → tras inserts |
|---|---|---|
| D1 | 21,5 → 42,9 MB (x2,0) | 14,4 → 28,8 MB (x2,0) |
| D2 | 8 → 17 MB | 14 → 28 MB |
| D3 | 9 → 22 MB | 14 → 20 MB |

1. **Los dos índices se duplican en D1.** El B-tree, construido con relleno del 90 %, parte todas sus hojas con inserciones de claves aleatorias y queda a media ocupación. ISAM agota su holgura del 20 % y reserva un bloque de overflow por cada bloque de datos. Tras las inserciones ISAM sigue siendo un 33 % más pequeño.
2. **En D2 ISAM es mayor desde el inicio** (14 MB contra 8 MB): el B-tree de PostgreSQL deduplica claves repetidas y ISAM guarda cada entrada. El ahorro de espacio de ISAM solo se cumple con claves únicas.
3. **Cómo se duplica ISAM:** al agotarse la holgura, cada bloque de datos recibe un bloque de overflow casi vacío (en D1 unas 50 entradas en un bloque de 679). El índice crece 8 KB por bloque aunque casi no haya datos nuevos. `make bench` ahora guarda `overflow_blocks` y `longest_chain` para verlo directamente (con `FILL=100` en una prueba pequeña: 147 bloques de overflow para 147 de datos, y el índice pasa de 1,17 a 2,32 MB).

## Construcción
Con 1 M de filas el B-tree tardó 172 a 177 ms y ISAM 188 a 201 ms (ISAM entre un 9 % y un 14 % más lento). En PostgreSQL 16 con una sola CPU, ISAM construyó el mismo millón de filas en unos 390 ms contra unos 800 ms del B-tree, así que la diferencia depende de la máquina. La hipótesis es que el B-tree usa construcción paralela y ISAM no. Para comprobarlo, `MAINT_WORKERS=0 make bench` fuerza la misma configuración para ambos.

## Experimento de overflow (D3, modo `dist`)
- `REINDEX` de `isam60` con 240 000 filas: 8 069 120 → 6 660 096 bytes (-17,5 %). **Restaura espacio, no eficiencia de consulta:** la latencia caliente pasa de 0,138 a 0,133 ms y los buffers de 176 a 175.
- Tras `REINDEX`, ISAM (6,35 MB) sigue siendo más grande que el B-tree reindexado (4,12 MB).
- El aumento de buffers (80 → 176) aparece **igual en el B-tree** (80 → 175). Se debe a que las inserciones añaden duplicados de las claves calientes y hay que leer más páginas del heap; no es evidencia de cadenas de overflow. En este experimento la cadena máxima es 1 o 2.
- Relleno 60 % retrasa el salto (sin overflow hasta 120 000 filas) a cambio de 3,86 MB iniciales frente a 2,90 MB del relleno 80 %.
- Para ver el efecto de las cadenas largas sobre la latencia hay que usar `INSERT_MODE=narrow DATASET=d1 make overflow`.

## Texto sugerido para el informe
> ISAM iguala al B-tree en lecturas de igualdad y rango (relación de tps entre 0,95 y 1,03, salvo el rango de D3 tras inserciones, 0,88) y en inserciones (0,98 a 1,03). Con claves únicas ocupa un 33 % menos espacio tras la construcción (14,4 contra 21,5 MB) y se mantiene un 33 % menor tras las inserciones masivas, aunque ambos índices duplican su tamaño: ISAM por los bloques de overflow y el B-tree por la partición de hojas. Con claves repetidas (D2) el B-tree es más compacto gracias a la deduplicación. La construcción de ISAM fue entre un 9 % y un 14 % más lenta que la del B-tree en 1 M de filas. La degradación específica de ISAM aparece cuando las inserciones se concentran en pocas claves, porque se forman cadenas de overflow y la latencia crece con su longitud; `REINDEX` o una política por umbral la corrige.

## Sobre la estabilidad
Las pruebas de integración, recuperación tras caída y carga concurrente pasan en 18.6. Conviene presentarlo con sus límites: clave `int4` de una columna, un insertador a la vez por índice, y sin `CREATE INDEX CONCURRENTLY` ni construcción paralela.
