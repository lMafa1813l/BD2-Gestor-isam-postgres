# Defensa y demostración de la Etapa I: bloques 0–6

La propuesta inicial es `docs/propuesta-inicial.pdf`. La estructura de la exposición
sigue los bloques internos del equipo; los bloques 7–8 y la distribución quedan
para la segunda etapa. Ajustar la duración al tiempo asignado por la profesora.

## Preparación y arranque exacto

Requisitos: Linux, Docker Engine con Compose v2, `gcc`, `make`, Python 3 y `flock`.
Python se utiliza para automatización; el núcleo y el AM están escritos en C.
La construcción descarga PostgreSQL 18.6 desde un commit oficial, comprueba
SHA-256 e instala paquetes Debian firmados por HTTPS. No requiere un token PGDG.

Desde una copia nueva del repositorio:

```bash
git clone https://github.com/lMafa1813l/BD2-Gestor-isam-postgres.git
cd BD2-Gestor-isam-postgres
make test
make integration
make demo
```

Usar la versión del repositorio que incluya el commit de correcciones de los
bloques 0–6 y el informe final.
`make integration` construye la imagen, inicializa el volumen cuando falta, verifica
PostgreSQL 18.6, ejecuta la integración y `tests/sql/caso-vacuum.sql`.
Los scripts `.sh` conservan su bit ejecutable en Git. No se necesita hacer chmod
manualmente en cada clon. El arranque tiene un límite de espera y muestra logs
si falla. El servidor está publicado solo en 127.0.0.1:5433.

Para demostrar un volumen nuevo sin borrar el existente:

```bash
export COMPOSE_PROJECT_NAME=isam_defensa
export ISAM_CONTAINER_NAME=isam_defensa_pg
export ISAM_PORT=5434
make integration
make demo
```

Estas variables dan a la demostración su propio volumen, contenedor y puerto.
Los datos de esa demo quedan conservados. No usar `down -v` sobre un volumen con
trabajo que se desee mantener. Los scripts bloquean operaciones concurrentes
contra el mismo contenedor; no matar/reiniciar un servidor mientras mide un benchmark.

## Guion de exposición (10–12 diapositivas)

1. **Objetivo:** demostrar una estructura alternativa propia y su uso real desde
   PostgreSQL; no afirmar que siempre supera al B-tree.
2. **Elección:** ISAM combina directorio estático, datos ordenados y overflow;
   explicar ventajas en datos estables y su límite frente a inserciones sesgadas.
3. **Layout:** dibujar META, DATA, INDEX y OVERFLOW. Cada entrada enlaza clave con
   TID del heap; no se copian las filas completas dentro del índice.
4. **Construcción:** leer el heap, ordenar entradas y construir niveles bottom-up.
5. **Consulta:** límites inferiores/superiores, descenso y recorrido de candidatos.
6. **Inserción:** localizar primario; rellenar espacio o añadir a la cola de overflow.
7. **Integración:** señalar SQL, opclass, handler, callbacks y buffer manager.
8. **Correctitud:** explicar pruebas y la regresión VACUUM, incluyendo su solución.
9. **Metodología:** D1/D2/D3, 100k/500k/1M, cinco repeticiones independientes,
   operaciones fijas, semillas, logs y mediana con dispersión.
10. **Resultados:** construcción, igualdad, rango, inserción y tamaño; distinguir
    resultados corregidos de los CSV exploratorios antiguos.
11. **Caso desfavorable:** cadenas largas, relleno, REINDEX y costo de la política.
12. **Límites y demo:** cerrar con el alcance de Etapa I y pasar a comandos en vivo.

## SQL listo para ejecutar

La secuencia autocontenida está en `tests/sql/demo.sql` y se ejecuta con `make demo`.
Para preguntas adicionales:

```bash
docker exec -it "${ISAM_CONTAINER_NAME:-isam_pg}" psql -X -U postgres -d bd2
```

```sql
SELECT version();
SELECT extversion FROM pg_extension WHERE extname='isam_am';
SET enable_seqscan=off;
EXPLAIN (ANALYZE, BUFFERS, COSTS OFF)
  SELECT * FROM demo_isam.items WHERE id=680;
SELECT * FROM demo_isam.items WHERE id=680;
SELECT count(*) FROM demo_isam.items WHERE id=99999;
SELECT * FROM demo_isam.items WHERE id BETWEEN 676 AND 684 ORDER BY id;
SELECT * FROM isam_index_stats('demo_isam.items_idx');
SELECT isam_reorg_needed('demo_isam.items_idx',25);
RESET enable_seqscan;
```

Durante `make demo` se insertan una fila superviviente de clave 680 y 10 000 filas
de clave 700, se borra únicamente la fila original 680 y se ejecuta VACUUM. Se debe
ver `superviviente` antes de REINDEX. Después de reorganizar deben verse cero
bloques de overflow. La GUC fill_pct permanece en 100 durante ese REINDEX.

Forzar `enable_seqscan=off` sirve para comprobar la ruta del índice en la demo;
no se fuerza en los benchmarks. `ORDER BY` es un ordenamiento SQL del resultado,
no orden garantizado por el AM, que declara `amcanorder=false`.

## Reinicio y recuperación en vivo

Cuando no haya un benchmark activo, un reinicio ordinario del contenedor:

```bash
docker restart "${ISAM_CONTAINER_NAME:-isam_pg}"
make demo
```

Las demostraciones de recuperación con SIGKILL y carga concurrente son:

```bash
make crash
make crash-load
```

`make crash` utiliza los SQL `crash_1.sql`/`crash_2.sql`; `make crash-load` utiliza
los SQL de carga y seis clientes. Comprueban consistencia índice/heap y el
comportamiento esperado de tablas UNLOGGED. No equivalen a demostrar recuperación
avanzada para toda secuencia posible ni preservación de transacciones no confirmadas.

## Preguntas individuales y respuestas sustentadas en código

**¿ISAM se reorganiza solo al insertar?** No. Los separadores del directorio son
estáticos. `isam_insert` añade entradas al primario o a overflow. REINDEX vuelve
a construir desde el heap. La política de umbral la ejecuta el runner, no un
proceso autónomo del servidor (`core/isam_insert.c`, `run_overflow.py`).

**¿Qué contiene el índice?** `IsamEntry` contiene int32, bloque del heap uint32,
offset uint16 y dos bytes reservados: 12 bytes. `IsamIndexEntry` ocupa 8 bytes
con separador y bloque hijo (`core/isam_layout.h`).

**¿Por qué 679 entradas por página y no 681?** En PostgreSQL hay 24 bytes de
cabecera PG y 16 de cabecera ISAM: floor((8192−24−16)/12)=679. En standalone
no hay cabecera PG: floor((8192−16)/12)=681.

**¿Dónde se construye?** `isam_ambuild` lee el heap mediante
`table_index_build_scan`, recoge TIDs, llama a `isam_sort_entries` y a
`isam_build_sorted` (`isam_am_build.c`, `core/isam_index.c`). La construcción
sobre entradas ordenadas es lineal; el flujo completo incluye ordenamiento.

**¿Por qué existen dos modos de descenso?** El inferior usa separadores `< clave`
para incluir candidatos anteriores cuando hay duplicados; inserción/último
candidato usan `<= clave`. Evita perder duplicados repartidos entre páginas.

**¿Cuál era el bug de VACUUM?** La primera clave actual de DATA se confundía con
su separador estático. VACUUM podía elevarla mientras overflow retenía claves
menores. `isam_scan_begin` ahora calcula el primer/último bloque candidato desde
los separadores de INDEX. El escaneo siempre visita la cadena antes de avanzar
o terminar (`core/isam_search.c`, `isam_index_range_blocks`).

**¿Por qué no se cambió VACUUM para mantener filas muertas?** Compactar entradas
muertas es correcto. El error estaba en la condición de finalización del lector.
`isam_ambulkdelete` traduce el callback de PostgreSQL y llama a `isam_delete_if`
(`isam_am_vacuum.c`, `core/isam_vacuum.c`).

**¿Qué hace amrescan?** Traduce operadores a límites y reinicia el estado. La
apertura/descenso ocurre de forma diferida en `isam_begin_if_needed`, al pedir
tuplas o bitmap (`isam_am_scan.c`).

**¿Cómo sabemos que no es un programa externo?** `CREATE ACCESS METHOD`, opclass
int4 y `IndexAmRoutine` enlazan SQL con callbacks C. EXPLAIN muestra Index Scan
o Bitmap Index Scan utilizando el índice creado (`isam_handler.c`, SQL 1.0).

**¿Implementaron un WAL propio?** No. Se reutiliza `GenericXLog` del DBMS; páginas
nuevas llevan imagen completa y las existentes deltas. No atribuir a esos deltas
una medición de `wal_compression` que no se haya realizado (`core/isam_io_pg.c`).

**¿Hay concurrencia completa?** No. Los insertadores se serializan con
`LockRelationForExtension`; VACUUM usa ese bloqueo. Las pruebas concurrentes
ejecutadas no sustituyen una demostración formal de todos los interleavings.

**¿Cómo se garantiza D2 único?** Se permutan los enteros 1..N usando semilla 0.42,
sin muestreo con reemplazo. D3 reutiliza exactamente D2; Zipf 1.1 se aplica a las
consultas (`datasets/d2.sql`, `d3.sql`, `workloads/w1_eq_uniform.pgb`).

**¿Qué significa una repetición independiente?** Recargar tabla, construir de
nuevo y reiniciar los workloads desde el mismo estado. Cada réplica registra su
build_ms. Las inserciones son exactamente N/10 y su huella se comprueba entre
alternativas (`benchmarks/run_bench.py`).

**¿Qué aporta el puntero a la cola?** Evita recorrer toda la cadena al insertar en
overflow. No acelera la consulta de toda la cadena y no reutiliza automáticamente
los huecos intermedios liberados por VACUUM (`chain_insert`, `find_tail`).

**¿Buffers significa lecturas físicas?** No. Los buffers incluyen hits y reads del
buffer manager. No deben presentarse automáticamente como accesos físicos al disco.

**¿Qué no soporta el AM?** Unicidad, múltiples columnas, index-only scan,
ordenamiento por índice, recorrido inverso y construcción paralela. No se reclama
soporte de CREATE INDEX CONCURRENTLY (`isam_handler.c`).

**¿Qué código es propio y qué se reutiliza?** La propuesta atribuye al equipo el
layout, núcleo, callbacks, generadores y harness. PostgreSQL, libc y herramientas
de compilación son externos. Las correcciones y documentación de esta entrega
tuvieron asistencia de Codex; el equipo debe revisar y poder explicar esa parte.

## Ensayo y respaldo

Cada integrante debe ejecutar la demo, localizar una función de cada capa y
explicar una comparación favorable y otra desfavorable. Conservar el PDF,
comandos, logs y CSV en el equipo de la demo. Si falla la infraestructura,
mostrar la evidencia guardada sin afirmar que el comando fallido pasó en vivo.
