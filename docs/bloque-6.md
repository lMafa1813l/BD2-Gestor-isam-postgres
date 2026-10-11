# Bloque 6: rendimiento a escala y ajustes de overflow

## Resumen
| Cambio | Antes | Después |
|---|---|---|
| Lecturas por inserción en una cadena de overflow de 38 bloques | 20,7 | **3,0** |
| WAL por 20 000 inserciones (tabla de 100 000 filas, índice ISAM) | 160 MB | **57 MB** (B-tree: 4,7 MB) |
| W2 | Zipf | Claves ausentes (rúbrica); el Zipf pasó a W5 |
| Visibilidad del overflow | solo desde C | `isam_index_stats()` y `isam_reorg_needed()` en SQL |

## Ajustes al Access Method

### 1. Puntero a la cola del overflow
Cada inserción en overflow recorría la cadena completa desde el bloque primario: costo proporcional al largo de la cadena (cuadrático al insertar muchas filas en pocas claves). Ahora el campo `level` de los bloques DATA (sin uso hasta ahora) guarda el último bloque de su cadena y la inserción va directo a él.
- Medido en el núcleo (50 000 inserciones sobre 100 claves, cadena de 38 bloques): 20,7 → 3,0 lecturas por inserción (índice + primario + cola).
- Compatibilidad: una cadena sin puntero (índice creado antes de este cambio) se detecta, se recorre una vez y se repara en la siguiente inserción.
- Contrapartida: el espacio que `VACUUM` libera en bloques intermedios de una cadena ya no se reutiliza hasta el siguiente `REINDEX`.

### 2. WAL delta
Dos problemas encontrados con `pg_waldump`:
1. Se escribía una imagen completa de 8 KB por cada escritura de bloque. Ahora solo las páginas nuevas llevan imagen completa y las existentes llevan deltas.
2. Aun con deltas, cada registro arrastraba una imagen completa: `PageInit` ponía a cero el `pd_lsn` de la copia de trabajo y PostgreSQL concluía que hacía falta una imagen. Ahora la cabecera solo se inicializa en páginas nuevas.

Resultado: 160 MB → 57 MB. El resto es el desplazamiento de entradas al insertar en orden dentro de un bloque primario (inherente al diseño). Una inserción masiva sigue costando unas 7 veces lo que un B-tree (≈350 ms contra ≈50 ms por 20 000 filas, en PostgreSQL 16 local).

### 3. Observabilidad (extensión versión 1.1)
```sql
SELECT * FROM isam_index_stats('idx');
-- n_keys, data_blocks, index_levels, overflow_blocks, chained_blocks, longest_chain, overflow_pct, total_pages
SELECT isam_reorg_needed('idx', 25);
```
Se actualiza con `ALTER EXTENSION isam_am UPDATE;` (los scripts de benchmark ya lo hacen, así que un volumen Docker existente sigue funcionando).

### 4. Política de reorganización
`REINDEX INDEX idx` reconstruye desde el heap y elimina todo el overflow. Política evaluada: reorganizar cuando `overflow_pct >= 25`. Es un umbral de espacio; para cargas sensibles a latencia conviene vigilar también `longest_chain`.

## Experimento de overflow (`make overflow`)
`benchmarks/run_overflow.sh` carga un dataset, construye el índice y aplica lotes de inserciones sesgadas, midiendo tras cada lote el tamaño del índice, el overflow, los buffers y la latencia de igualdad sobre las claves calientes. Configuraciones (`CONFIGS`): `btree`, `isam<relleno>` (por ejemplo `isam60`, `isam80`, `isam100`) e `isam<relleno>t<umbral>` (por ejemplo `isam80t25`: reorganiza automáticamente al superar el umbral).

Dos modos de inserción (`INSERT_MODE`):
- `dist` (por defecto): la distribución de D3 (80 % en el 1 % del dominio).
- `narrow`: todas las claves nuevas en una ventana de 100 claves (`WINDOW`), pensado para datos con claves únicas (`DATASET=d1`).

### Resultados de muestra (PostgreSQL 16 local; N = 200 000; indicativos)

**Modo `dist` sobre D3** (200 000 filas insertadas):
- El overflow aparece en casi todos los bloques (≈99 % de overflow), pero con **cadenas de 1 a 2 bloques**: la zona caliente de D3 abarca ~80 % de los datos y se reparte en casi todo el índice.
- El costo es de **espacio**: índice de 5,8 MB (ISAM al 80 %) frente a 3,9 MB (B-tree).
- La latencia de igualdad caliente es equivalente a la del B-tree (domina la lectura del heap por las claves duplicadas).
- `isam80t25` reorganizó dos veces y mantuvo el overflow en 0 %, con un índice entre 4,0 y 5,2 MB.

**Modo `narrow` sobre D1** (100 000 filas insertadas en 100 claves):
| config | latencia igualdad caliente | buffers | cadena máxima |
|---|---:|---:|---:|
| B-tree | 0,63 ms | 606 | - |
| `isam80` sin reorganizar | **1,21 ms** | 754 | 148 |
| `isam80` tras `REINDEX` | 0,64 ms | 608 | 0 |
| `isam80t25` (política) | 0,51 ms | 489 | 0 |

Es la degradación que anticipaba la propuesta para accesos sesgados: la latencia crece linealmente con la cadena (de 0,04 a 1,21 ms) y `REINDEX` la restablece. Con una cadena del 24 % de overflow ya se pierde 1,9 veces frente al B-tree.

### Conclusiones para el informe
1. ISAM iguala al B-tree en lectura (igualdad y rango), construye más rápido y es más compacto en datos estáticos.
2. Su punto débil es la escritura: inserciones masivas ≈ 4 a 7 veces más lentas y más WAL.
3. La degradación por overflow depende de **cómo se concentran** las inserciones: reparto amplio cuesta espacio; concentración en pocas claves cuesta latencia.
4. Una política de reorganización por umbral basta para acotar ambos efectos.

## Cómo reproducir
```
make bench                                   # sin índice vs B-tree vs ISAM
REPS=3 N=1000000 T=20 make bench             # a mayor escala, con repeticiones
make overflow                                # modo dist sobre D3
INSERT_MODE=narrow DATASET=d1 make overflow  # cadenas largas
make report                                  # tablas Markdown y PNG en benchmarks/results/
make crash-load                              # caída bajo carga concurrente
```

## Pruebas nuevas
- `make test`: 117 658 verificaciones en el núcleo (pruebas del puntero a la cola, de la compatibilidad con cadenas sin puntero y del conteo exacto de `isam_index_stats`).
- `make integration`: estadísticas de overflow, `isam_reorg_needed`, error al consultar un índice que no es ISAM y reorganización con `REINDEX`.
- `make crash-load`: `kill` del servidor con 6 clientes insertando; tras la recuperación el índice coincide con el heap.

## Estado de verificación
Probado en PostgreSQL 16.15: integración, recuperación tras caída, concurrencia con `pgbench`, `kill -9` en plena carga, ruta de actualización 1.0 → 1.1. Pendiente en 18.6: `make integration`, `make crash`, `make crash-load`, `make overflow` y `make bench`.
