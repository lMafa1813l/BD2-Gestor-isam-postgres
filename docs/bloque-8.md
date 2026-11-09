# Bloque 8: ejecución distribuida y evidencia

El contrato de diseño y sus criterios de aceptación están en [bloque-7.md](bloque-7.md).
El Gantt original se conserva como [gantt-original.pdf](gantt-original.pdf); sus
responsables son una planificación, no una atribución verificada de los cambios.

## Preparar el entorno

Requisitos: Linux, Docker Engine/Compose v2, Python 3.10+, `venv`, `make`, `flock`.
La compilación de los componentes C ocurre dentro de Docker. Para las tablas y
gráficas se usa matplotlib (`requirements-report.txt`); para el PDF, TeX Live y
latexmk. Los puertos 55431–55433 deben estar libres.

```bash
python3 -m venv .venv-dist
.venv-dist/bin/pip install -r distributed/requirements.txt
make dist-up
make dist-smoke
make dist-validate
```

`dist-up` construye, cuando falta, la imagen PostgreSQL 18.6 + ISAM y compila
`contrib/postgres_fdw` desde el mismo commit oficial verificado. La primera
construcción puede tardar varios minutos. Los siguientes arranques reutilizan la
imagen. No se modifica la imagen ni el volumen de la Etapa I al levantar el
proyecto `bd2_dist`. Cada nodo posee un volumen persistente independiente y solo
se publican puertos en 127.0.0.1. La contraseña se genera al primer arranque y se guarda localmente en
`.secrets/<proyecto>.password` con permisos 600. Ese directorio está excluido de
Git y del contexto de construcción. Conservar el archivo junto con los volúmenes;
no publicar su contenido ni sustituirlo mientras se reutilicen esos datos.

```bash
make dist-setup                            # 1M pedidos, regional, ISAM
make dist-setup DIST_ARGS='--strategy hash --index btree'
make dist-demo
./distributed/run.sh status
make dist-stop                             # conserva los tres volúmenes
make dist-up
```

`setup` recarga exclusivamente la base `distrib`, esquemas `dist`/`remote_*`
identificados como pertenecientes al laboratorio. No es un comando para bases
con datos a conservar. Un esquema existente sin la marca del laboratorio se
rechaza. Los comandos no utilizan `down -v`. Para una instalación adicional se
pueden usar `DIST_PROJECT=otra_prueba DIST_PORT_BASE=55531` en todos los comandos.
El hostname FDW `pg-a`, `pg-b`, `pg-c` se resuelve dentro de la red de cada proyecto.

## Esquema y operaciones

`db.py` genera clientes y productos en A y copia ambos catálogos a B/C mediante
COPY. Genera pedidos y detalles directamente en cada propietario mediante
`generate_series`; los predicados CHECK y las PK/FK locales comprueban la ubicación
y los vínculos. `regional` usa la región del cliente; `hash` usa la mezcla modular
especificada en el bloque 7. Cada pedido tiene un detalle, con precio histórico.
Los cambios posteriores del catálogo no recalculan facturas anteriores.

```bash
docker exec -it bd2_dist_a psql -X -U postgres -d distrib
```

```sql
SELECT version();
SELECT count(*) FROM dist.orders;       -- fragmento A
SELECT count(*) FROM dist.all_orders;   -- unión real por FDW
SELECT count(*) FROM remote_b.orders;   -- fragmento B desde A
SELECT * FROM dist.replica_state;
EXPLAIN (ANALYZE, VERBOSE, BUFFERS)
  SELECT count(amount_cents) FROM dist.orders WHERE customer_id=1;
EXPLAIN (ANALYZE, VERBOSE)
  SELECT count(*) FROM remote_b.orders;
SELECT count(*), sum(i.quantity*i.unit_price_cents)
FROM remote_c.orders o
JOIN remote_c.order_items i ON i.order_id=o.id
JOIN dist.customers c ON c.id=o.customer_id
JOIN dist.products p ON p.id=i.product_id;
```

Las conexiones de psycopg desactivan la preparación automática para conservar el
mismo protocolo entre ensayos. Los parámetros de búsqueda se convierten a `int4`:
la clase de operadores de nuestro ISAM no incluye comparaciones cruzadas
`int4`/`int2`. No se fuerza el plan en la carga medida. `plans.json` conserva tanto
el plan normal como un diagnóstico separado con `enable_seqscan=off`; este último
comprueba que el índice implementado pueda utilizarse. La PK B-tree de `id` existe
en todas las configuraciones; `none` significa sin índice secundario de cliente.

## Prueba rápida y aceptación

`dist-smoke` ejecuta 4 ensayos pequeños por defecto: dos estrategias y dos
perfiles, con ISAM, N=6000 y una réplica de 10 operaciones. Se distingue con
`smoke=true` y no sustituye resultados oficiales. Para probar las combinaciones:

```bash
make dist-bench DIST_ARGS='--smoke --n 6000 --reps 1 --ops 10 --latency-modes base model --out distributed/results/mi_smoke'
make dist-validate DIST_ARGS='--n 6000 --reps 1 --out distributed/results/mi_validacion'
```

La validación comprueba sumas contra una referencia Python, huellas del contenido,
identificadores únicos 1..N, localización, FK y una unión de cuatro tablas entre
nodos. Antes y después de la carga se verifican los incrementos confirmados de
`status`; cada lectura también se compara con una referencia que conoce las
escrituras anteriores.

La aceptación muestra: producto modificado en A; B/C aún conservan el precio
anterior; refresco explícito y convergencia de precio/versión. Detiene realmente C,
comprueba catálogos y fragmentos locales A/B y una escritura confirmada en A;
exige que fallen el total global y la escritura hacia C. Reinicia C incluso si
una aserción falla y vuelve a verificar los datos. No existe failover automático
ni réplica de pedidos; no se entrega silenciosamente un total global parcial.

## Experimentos oficiales

```bash
make dist-bench DIST_ARGS='--out distributed/results/mi_modelo'
make dist-bench DIST_ARGS='--configs isam --profiles balanced --latency-modes base --out distributed/results/mi_control'
make dist-validate DIST_ARGS='--official --n 1000000 --reps 5 --out distributed/results/mi_aceptacion'
```

El experimento principal tiene 60 ensayos: 2 estrategias × 3 índices secundarios ×
2 perfiles × 5 repeticiones. Cada ensayo recarga 1M pedidos y detalles, reconstruye
sus índices y ejecuta 100 operaciones: 50 lecturas por cliente, 20 rangos de 100
identificadores y 30 actualizaciones `status=status+1`. Las PK resuelven los
rangos y actualizaciones; el secundario se evalúa en las lecturas por cliente.

La secuencia se genera con semilla `42000+réplica` y su SHA-256 debe coincidir entre
estrategias e índices. El perfil `balanced` elige origen/región con pesos 1:1:1;
`hot_c` usa 1:1:8. La proporción realizada se conserva en los resultados y puede
variar en una muestra de 100 operaciones. El cliente ejecuta secuencialmente:
este cambio de concentración no demuestra saturación bajo concurrencia.

El control adicional contiene 10 ensayos, con ISAM y perfil equilibrado, sin
espera artificial. La aceptación oficial repite cinco veces cada estrategia,
con 1M pedidos: 10 escenarios de réplica, fallo y recuperación. La recarga y
validación repetidas consumen mucho más tiempo que las 100 operaciones; reservar
varios minutos por bloque de ensayos, o decenas de minutos para la matriz completa,
según la máquina. No lanzar estos comandos simultáneamente contra el mismo proyecto.

## Latencia y bytes

El modo `model` interpreta A–B=20, A–C=40 y B–C=25 ms como un costo RTT por destino
remoto solicitado y suma esos costos antes de ejecutar SQL. Una lectura local
no recibe espera. Una consulta a B y C desde A añade 60 ms. FDW sí ejecuta la
consulta real; el retraso es una simulación en el cliente, no una modificación de
la red. No representa todas las rondas del protocolo, ancho de banda o congestión.

Se guardan `model_ms` solicitado, `db_ms` observado y `elapsed_ms`, que incluye
espera efectiva y SQL. La diferencia entre total y SQL también incluye el
sobrecosto y la precisión de la espera del sistema operativo. El modo `base`
utiliza exactamente el mismo SQL y operaciones sin esa espera añadida.

Los contadores RX/TX de eth0 se leen por nodo antes y después del tramo de carga,
fuera de la recarga y validación. Incluyen tráfico SQL del cliente, FDW y protocolo.
RX+TX cuenta ambos extremos de algunos enlaces; no debe presentarse como volumen
único de filas transmitidas. El tamaño JSON del resultado es una métrica lógica
separada. La actividad del host y el orden fijo de alternativas siguen siendo
amenazas a la validez; el protocolo no garantiza aislamiento ni cachés idénticas. La validación abre
conexiones FDW antes del tramo medido; se evalúan conexiones ya establecidas.

## Evidencia y regeneración

Cada corrida escribe CSV, metadatos y carpetas de ensayo con operaciones, planes,
validaciones y deltas por nodo. La ruta de salida debe ser nueva. Un fallo deja
`status=failed`; solo `completed`, sin `smoke`, se acepta como evidencia oficial.
Los resúmenes comprueban la cuadrícula, cinco repeticiones, huellas, cuotas y hashes.

La entrega conserva las corridas verificadas en `docs/results/distributed/`:
`model/`, `base/` y `acceptance/`. Los artefactos extensos se conservan en archivos
`evidence.zip`, con las rutas y hashes descritos por sus metadatos. Las copias antiguas de
fuentes con credenciales fijas de laboratorio se retiraron durante la revisión
previa a publicación; las mediciones y planes permanecen intactos. Ver
`docs/results/distributed/publication.md`.

```bash
make dist-report
make pdf-final
```

Los CSV de la Etapa I permanecen en sus rutas originales y no se mezclan con los
distribuidos. `make report` ahora genera una vista previa de la Etapa I en
`.cache/stage1-report/`, sin sobrescribir esos CSV ni las figuras oficiales.
`make pdf` compila `Informe_IEtapa.tex`; `make pdf-final` compila `Informe_Final.tex`.

## Mapa de código para revisar y defender

| Función | Recibe | Operación y resultado |
|---|---|---|
| `db.owner` | id de pedido y estrategia | Aplica región o mezcla modular y devuelve A/B/C |
| `db.setup` | conexiones, N, estrategia e índice | Comprueba propiedad del laboratorio, crea esquema, genera catálogos/fragmentos, índices y FDW; devuelve tiempos y tamaños por nodo |
| `db.validate` | conexiones, N, estrategia y escrituras esperadas | Contrasta FK, ubicación, conteos, sumas, identificadores y huellas con el oráculo; devuelve evidencia o falla con una aserción |
| `db.refresh_products` | conexiones a A/B/C | Lee snapshot de A y publica precios/versión en cada réplica; devuelve versión y tiempos por suscriptor |
| `experiment.operations` | N, cuota, semilla y perfil | Genera exactamente 50% lecturas de cliente, 20% rangos y 30% escrituras |
| `experiment.query_for` | operación y estrategia | Construye SQL local/FDW y devuelve parámetros y destinos; usa conversiones `int4` |
| `experiment.run_trial` | conexiones y condición | Recarga, valida, guarda planes, mide carga y bytes, contrasta resultados y escrituras; devuelve la fila CSV |
| `validate.scenario` | conexiones, N y estrategia | Demuestra retraso/convergencia de catálogos y fallo/recuperación reales de C |
| `summarize.load` | una corrida guardada | Rechaza diagnósticos, corridas incompletas, cuotas o hashes incorrectos antes de resumir |

Duración observada de estas corridas, incluyendo recarga y validación: matriz principal: 22.9 minutos; control: 3.2 minutos; aceptación: 5.3 minutos. Son referencias de esta máquina, no tiempos garantizados.

La regresión SQL de la Etapa I se ejecutó en un proyecto separado, porque ese
script recrea su extensión y objetos de prueba:

```bash
COMPOSE_PROJECT_NAME=bd2_stage1check \
ISAM_CONTAINER_NAME=bd2_stage1check_pg ISAM_PORT=55440 make integration
docker stop bd2_stage1check_pg
```

El contenedor y volumen originales de la Etapa I se conservaron. El lanzador de
integración exige ahora la marca de finalización para detectar una salida
anticipada de psql que no complete sus comprobaciones.
