# Defensa final: indexación y distribución

La guía de la Etapa I permanece en `docs/defensa.md`; esta guía añade el escenario
de las secciones 6.3 y 6.3.1 de la rúbrica. Los cinco integrantes deben poder
explicar el sistema completo. El Gantt muestra la planificación original; no
acredita por sí solo la autoría de los cambios.

## Guion recomendado

1. Mostrar cuatro relaciones, claves y un millón de pedidos: distinguir la cantidad
   lógica de las copias de catálogos.
2. Dibujar A/B/C y explicar el predicado `regional` y la mezcla modular `hash`.
   Un pedido y su detalle comparten propietario; PK/FK se comprueban localmente.
3. Mostrar una consulta local y un `Foreign Scan`. PostgreSQL ejecuta FDW real;
   los resultados no provienen de archivos exportados.
4. Explicar catálogos: fuente A, copias reales B/C, retraso hasta refresco y
   transacción por réplica. Los precios históricos de facturas no se recalculan.
5. Explicar el índice secundario variable: las PK B-tree permanecen para todas las
   alternativas. ISAM no impone unicidad ni reemplaza las PK.
6. Mostrar la misma secuencia de 70 lecturas/30 escrituras con región y hash.
   Justificar qué consultas necesitan varios nodos y enseñar sus hashes de entrada.
7. Presentar las medianas e IQR; separar SQL observado de la espera 20/40/25 ms
   simulada. Interpretar RX/TX como tráfico de protocolo, cliente y FDW.
8. Explicar perfil concentrado y falla de C: disponibilidad local, error global
   visible y ausencia de failover. Concluir con límites y evidencia conservada.

## Demostración

```bash
make dist-up
make dist-setup              # recarga el laboratorio, 1M, regional + ISAM
make dist-demo
```

En A:

```bash
docker exec -it bd2_dist_a psql -X -U postgres -d distrib
```

```sql
SELECT count(*) FROM dist.orders;
SELECT count(*) FROM dist.all_orders;
SELECT count(*) FROM remote_b.orders;
EXPLAIN (ANALYZE, VERBOSE)
  SELECT count(*) FROM remote_b.orders;
EXPLAIN (ANALYZE, BUFFERS)
  SELECT count(amount_cents) FROM dist.orders WHERE customer_id=1;
SELECT * FROM isam_index_stats('dist.orders_customer_idx');
```

Cambiar asignación y repetir las consultas; el total global debe conservarse:

```bash
make dist-setup DIST_ARGS='--strategy hash --index isam'
make dist-demo
```

La prueba de aceptación contiene el guion automatizado completo de réplica,
indisponibilidad y recuperación, y recarga su propio laboratorio:

```bash
make dist-validate
```

Para observar manualmente la réplica tras `make dist-setup`:

```bash
.venv-dist/bin/python - <<'PY'
import sys
sys.path.insert(0, 'distributed')
import db
c = db.connect_all()
try:
    def show():
        for node, conn in c.items():
            print(node, conn.execute('SELECT price_cents FROM dist.products WHERE id=1').fetchone())
    c['a'].execute('UPDATE dist.products SET price_cents=price_cents+17 WHERE id=1')
    show()                  # A cambió, B/C conservan la copia anterior
    print(db.refresh_products(c))
    show()                  # convergencia real de las copias
finally:
    for conn in c.values(): conn.close()
PY
```

Ejecutar las demostraciones cuando no haya benchmarks activos. Los targets
adquieren un bloqueo por proyecto; el ejemplo manual de Python presupone que
nadie más está usando el laboratorio.

## Preguntas y respuestas

**¿Qué se distribuye y qué se replica?** Pedidos y detalles se fragmentan y se
colocan juntos; clientes y productos tienen copias completas. Los pedidos no
están replicados. El bloque 7 y `db.owner()` definen la asignación.

**¿Por qué esta función hash?** El resto directo de id entre tres quedaba
correlacionado con el ciclo de 3.000 clientes del generador. La mezcla modular
rompe esa correlación y permite que las búsquedas de un cliente encuentren pedidos
en varios nodos. Es una elección reproducible para este escenario, no criptográfica.

**¿La vista global garantiza una transacción distribuida?** No. FDW solicita
fragmentos de varios servidores; no añade por sí solo un protocolo global de
confirmación atómica ni una instantánea MVCC común. El experimento usa un cliente
secuencial y escrituras dirigidas a un propietario.

**¿Cómo prueban las relaciones?** Hay PK/FK locales; el validador contrasta
conteos, sumas, huellas, propiedad e identificadores únicos con una referencia
Python. También ejecuta una unión remota de cuatro tablas.

**¿Qué ocurre al detener C?** A/B conservan datos locales y catálogos. La consulta
global y una escritura que necesita C fallan. Tras reiniciar C se comprueban
contenido y la escritura local confirmada. No hay promoción automática.

**¿Los 20/40/25 ms se midieron físicamente?** Son parámetros de la rúbrica
interpretados como RTT y simulados mediante espera aditiva por destino remoto.
El tiempo SQL y los bytes FDW sí se observan en la ejecución real. El modelo no
incluye cada ronda del protocolo, congestión ni ancho de banda.

**¿Los bytes RX+TX son bytes útiles únicos?** No. Incluyen protocolo y tráfico
cliente/FDW, y pueden contar dos extremos del mismo enlace. Se guardan por nodo;
el tamaño lógico del resultado es una métrica distinta.

**¿Qué significa `none`?** Ausencia del índice secundario de cliente. Las PK
B-tree permanecen para unicidad, FK y operaciones por id en todos los casos.

**¿Cómo demuestran el uso de ISAM?** Se guardan planes normales y un diagnóstico
forzado separado. Las claves se convierten a int4; la clase de operadores
académica no incluye comparaciones int4/int2. El benchmark deja elegir al planner.

**¿Qué cambió en la carga?** Origen y región pasan de pesos 1:1:1 a 1:1:8 hacia C.
La proporción realizada queda registrada. La ejecución secuencial no demuestra
cómo se comportaría el sistema saturado por clientes concurrentes.

**¿Qué se puede concluir?** Interpretar solo las condiciones de las tablas:
una asignación que evita accesos remotos para esta carga puede reducir el costo
modelado. Los tiempos SQL, los índices y la red aportan costos distintos; no se
afirma superioridad universal ni alta disponibilidad de todos los datos.

## Estudio por integrante

El reparto siguiente es una recomendación de estudio: Fabian, entorno/FDW;
Bryan, reglas y restricciones de fragmentación; Andy, consultas/planes e índices;
Jorge, snapshots/fallos/validación; Leonardo, cargas/mediciones e interpretación.
Cada persona debe ejecutar la demo completa y explicar las limitaciones del modelo.
