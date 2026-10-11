# Bloque 3: inserción con overflow

## API (`isam_am/core/isam_insert.[ch]`)
| Función | Qué hace |
|---|---|
| `isam_insert(f, entry)` | Inserta una entrada. Archivo abierto con `writable = 1`. |
| `isam_stats(f, &st)` | Bloques DATA, bloques overflow, bloques con cadena y cadena más larga. No altera `n_reads`. |
| `isam_needs_reorg(f, pct)` | Verdadero si `bloques overflow / bloques DATA >= pct %`. |
| `isam_reorganize(f, path)` | Relee todo, ordena y reconstruye el archivo con el mismo `fill_pct`. Elimina el overflow. |
| `isam_sync(f)` | Persiste el META. `isam_close` lo hace solo si hubo cambios. |

## Algoritmo de inserción
1. Descenso con `ISAM_DESCEND_UPPER` (último separador <= clave) hasta el bloque DATA.
2. Si el bloque primario tiene espacio (capacidad completa de 681, no el `fill_pct`), inserta en orden.
3. Si está lleno, recorre su cadena de overflow y agrega al final del primer bloque con espacio.
4. Si toda la cadena está llena, asigna un bloque overflow nuevo al final del archivo y lo encadena.

## Invariantes
- Los separadores del índice no cambian después de construir (el índice es estático).
- Todo bloque primario sigue ordenado; las entradas de overflow no lo están.
- Toda entrada de un bloque y de su cadena es >= al separador del bloque, así que el corte de rangos del Bloque 2 sigue valiendo.

## Costo observado (carga sesgada, 150 000 claves)
| Situación | Lecturas por igualdad |
|---|---|
| Clave fría | 2 |
| Clave caliente con cadena de 38 bloques | 38 |
| Clave caliente tras `isam_reorganize` | 3 |

## Umbral de reorganización
Es la mitigación de la propuesta para la carga sesgada (D3). La política se decide en quien llama; un valor razonable de partida es `isam_needs_reorg(f, 25)`. Documentar como limitación conocida que la reorganización es total y bloqueante.

## Pruebas
`make test` ahora corre `test_isam_core` (3774 verificaciones) y `test_isam_insert` (66 995): índice vacío, inserción sin overflow, overflow uniforme con extremos int32, carga sesgada con reorganización, y persistencia con archivo de solo lectura.

## Pendiente para el Bloque 4
El núcleo usa `pread/pwrite` sobre un archivo. Dentro de PostgreSQL cada bloque debe vivir en una página de la relación del índice (buffer manager), así que `isam_io.c` se reemplaza por una capa equivalente sobre `ReadBuffer`/`ExtendBufferedRel`. El resto del núcleo no cambia.
