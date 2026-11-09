# Matriz de requisitos y evidencia de la entrega final

La matriz corresponde al código y a las corridas archivadas de esta entrega.
Los bloques internos 7–8 abarcan las actividades 7–10 del Gantt original. Una
prueba técnica aprobada no sustituye la defensa individual exigida por el curso.

| Requisito | Implementación / comprobación | Evidencia |
|---|---|---|
| ISAM propio integrado en PostgreSQL | Núcleo C, IndexAmRoutine y opclass int4; regresión vigente | `isam_am/`, logs de regresión en `execution-logs.zip` |
| Comparación del índice con B-tree y sin índice | D1/D2/D3, 100k/500k/1M, cuotas W1–W4, cinco réplicas de las corridas históricas corregidas | `docs/results/bench_corrected.csv/.json` y `overflow_corrected.csv/.json`, preservados |
| Caso favorable y desfavorable del índice | Datos estables frente a concentración de overflow y reorganización | Informe de Etapa I y resultados corregidos; no se presentan como mediciones distribuidas nuevas |
| Tres PostgreSQL 18.6 en Docker | A/B/C, red propia, volúmenes persistentes y puertos independientes | `distributed/compose.yml`, versión e imágenes en metadatos oficiales |
| Cuatro relaciones vinculadas | Clientes, productos, pedidos y detalles; PK/FK locales | `distributed/db.py`, validaciones de relaciones y join de cuatro tablas |
| Relación principal con al menos 1M filas | 1M pedidos y 1M detalles lógicos por ensayo oficial | CSV y validaciones `model/`, `base/`, `acceptance/` |
| Fragmentación y asignación justificadas | Región del cliente frente a mezcla hash del identificador; detalles colocados con pedidos | `docs/bloque-7.md`, `db.owner`, CHECK y validación global |
| Dos estrategias comparadas | Datos y secuencia lógica idénticos; 60 ensayos principales | `model/trials.csv`, SHA de operaciones y huellas iniciales |
| Replicación explicada y demostrada | Copias reales de catálogos; snapshots explícitos A→B/C, versión y transacción por réplica | Diez escenarios oficiales de retraso y convergencia en `acceptance/` |
| Consultas locales y entre nodos | Tablas locales, servidores postgres_fdw y vistas globales | `plans.json` en los ZIP de evidencia; operaciones y validaciones FDW |
| B-tree e ISAM respaldados por planes | PK B-tree siempre; secundario de cliente variable; plan normal y diagnóstico separados | 60 planes normales locales con secundario ISAM, 60 con B-tree; otros 60 sin secundario |
| Latencias 20/40/25 ms | Modelo RTT aditivo por destino remoto, aplicado mediante espera del cliente | `model_ms`, `db_ms` y `elapsed_ms` separados; control `base/` sin espera añadida |
| Carga 70/30 | 50 lecturas por cliente, 20 rangos y 30 actualizaciones por cada 100 operaciones | 7.000 operaciones en 70 ensayos oficiales; cuota y estado final verificados |
| Cambio de concentración | Pesos 1:1:1 frente a 1:1:8 hacia C; proporción realizada registrada | Perfiles `balanced`/`hot_c` y columna `origin_c_operations` |
| Indisponibilidad de un nodo | Detención real de C; lecturas A/B y escritura A continúan; total global y escritura C fallan; reinicio y verificación | Diez escenarios oficiales en `acceptance/`, dos fallos esperados por escenario |
| Latencia y transferencia observables | Tiempo SQL real, tiempo total y espera simulada; RX/TX por nodo y bytes lógicos del resultado | CSV, `trial.json`, resumen y definición precisa en `docs/bloque-8.md` |
| Al menos cinco repeticiones por medición | Cinco por condición principal y control; cinco aceptaciones por estrategia | Metadatos y `validation.json`; mediana e IQR inclusivo |
| Correctitud entre estrategias y referencia | Conteos, unicidad, sumas y huellas; referencia Python por operación y escrituras confirmadas | `db.validate`, `expected_result`, `final-lab-check.json` |
| Reproducibilidad y protección del trabajo previo | Build con versión/commit/checksum, scripts, semillas y salidas exclusivas; volúmenes distintos | README, `run.sh`, fuentes y hashes archivados |
| Informe final y referencias | Diseño del índice, integración, metodología, resultados, distribución, fallos, discusión, límites y recursos | `Informe_Final.tex/.pdf`, `docs/defensa-final.md` |
| Planificación y contribuciones | Gantt conservado como antecedente; recursos externos declarados | `docs/gantt-original.pdf`, propuesta y declaración del informe final |
| Comprensión y defensa individual | Guion, comandos y preguntas; cada integrante debe explicarlos y ejecutarlos | `docs/defensa.md` y `docs/defensa-final.md`; evaluación docente pendiente |

## Alcance que debe explicarse

La ejecución SQL/FDW, los tres servidores y las copias de catálogos son reales.
Las latencias de los enlaces se simulan; no se ha configurado una WAN física ni
`netem`. Las PK B-tree permanecen en todos los casos. Los pedidos no se replican;
no existe failover automático, consenso, confirmación atómica global ni snapshot
MVCC común entre nodos. La prueba usa un cliente secuencial y una parada de C
sin escrituras en vuelo. No caracteriza transacciones inciertas ni saturación.

Las cifras distribuidas provienen de estas corridas oficiales completas; los
resultados históricos del índice se identifican por separado. Los diagnósticos
fallidos iniciales se conservan como tales en el archivo de logs: permitieron
identificar y corregir el tipo `int2` de parámetros frente a la opclass `int4`.

## Reproducir

Seguir `README.md` y `docs/bloque-8.md`. Para generar un resumen de corridas nuevas,
conservar sus carpetas completas y elegir explícitamente los tres inputs:

```bash
MPLCONFIGDIR=.cache/matplotlib python3 distributed/summarize.py \
  distributed/results/mi_modelo distributed/results/mi_control \
  --validation distributed/results/mi_aceptacion \
  --out docs/results/distributed
make pdf-final
```

Este último comando actualiza las tablas generadas del informe, no los CSV
oficiales archivados. La discusión debe revisarse si se sustituyen las corridas.
