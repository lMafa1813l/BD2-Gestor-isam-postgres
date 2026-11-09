# Bloque 7: contrato del diseño distribuido

Este diseño aplica las secciones 6.3–6.3.1 y 8–11 de la rúbrica. Los bloques
internos 7–8 abarcan las actividades 7–10 del Gantt original: diseño,
implementación/simulación, comparación y entrega. Las asignaciones del Gantt
son planificación histórica, no acreditan quién realizó cada cambio actual.

## Esquema, claves y generación

Se modela una tienda con cuatro relaciones vinculadas. Las cantidades se refieren
al conjunto lógico, no a la suma de copias replicadas.

| Relación | Clave y relaciones | Datos y ubicación |
|---|---|---|
| `customers` | `id` PK, `region` en 0/1/2 | 3.000 clientes; copia completa en A/B/C |
| `products` | `id` PK | 1.000 productos; A es fuente autoritativa, copias en B/C |
| `orders` | `id` PK; `customer_id` FK a clientes | Relación principal: N=1.000.000 en experimentos oficiales |
| `order_items` | `order_id` PK/FK a pedidos; `product_id` FK a productos | Un detalle por pedido; mismo propietario que el pedido |

Para un pedido con identificador `i` entre 1 y N:

- `customer_id = 1 + ((i - 1) % 3000)`.
- `region = (customer_id - 1) // 1000`.
- El cliente conserva siempre esa región; la región del pedido es derivada.
- Las demás columnas se generan por expresiones deterministas del identificador.
- Las operaciones experimentales usan semillas guardadas, iguales entre alternativas.

Las PK son B-tree en todas las configuraciones y hacen cumplir unicidad y FK.
La comparación `none/btree/isam` se aplica exclusivamente al índice secundario
`orders.customer_id`. `none` significa **sin ese índice secundario**, no ausencia
absoluta de índices. Este alcance evita atribuir a ISAM capacidades de unicidad
que el AM académico no implementa.

## Dos fragmentaciones y su asignación

Se numeran A=0, B=1 y C=2.

| Estrategia | Predicado de propietario | A | B | C |
|---|---|---|---|---|
| `regional` | `owner(i) = region(i)` | Región 0 | Región 1 | Región 2 |
| `hash` | `h(i) = ((i*1103515245+12345) % 2147483647) % 3` | h(i)=0 | h(i)=1 | h(i)=2 |

La mezcla modular de `hash` evita que el ciclo de 3.000 clientes concentre todos
los pedidos de un cliente en un único residuo. No es una función criptográfica.

Ambas reglas son funciones totales y deterministas: cada pedido pertenece a un
único fragmento, todos los pedidos están cubiertos y la unión reconstruye la
relación lógica. Los detalles heredan la fragmentación de su pedido. Cada nodo
puede aplicar sus FK de forma local porque conserva ambos extremos del vínculo,
además de copias de los catálogos.

`regional` busca cercanía entre una sede y sus clientes. Una carga concentrada en
la región C puede concentrar trabajo en C. `hash` distribuye identificadores entre
tres nodos, pero la consulta de un cliente puede requerir los tres fragmentos.
No se supone a priori una estrategia ganadora; ambas ejecutan la misma secuencia
lógica de operaciones.

## Ejecución distribuida real

Los tres PostgreSQL 18.6 corren en contenedores con volúmenes propios del proyecto
Compose `bd2_dist`, separados de los de la Etapa I. En cada nodo, el esquema
`dist` contiene tablas locales. Los esquemas `remote_a`, `remote_b` y `remote_c`
exponen por `postgres_fdw` las tablas de los otros nodos. Las vistas
`all_orders` y `all_order_items` reconstruyen las relaciones con `UNION ALL`.

Una consulta dirigida puede usar una tabla local o una tabla extranjera. Una
consulta global solicita datos de más de un servidor. PostgreSQL transmite
consultas y resultados mediante FDW; no se representa esta ejecución como una
simple suma de resultados previamente exportados. El cliente conoce la regla de
propiedad y dirige las escrituras a un único propietario.

No se ofrece una transacción global con confirmación atómica entre nodos. Las
operaciones de escritura del experimento modifican un pedido en su propietario.
Las restricciones locales no sustituyen una restricción global para escrituras
arbitrarias que eludan el encaminamiento implementado.

## Replicación de catálogos

Los clientes son un catálogo inmutable durante la medición. Los productos se
replican mediante **copias reales de snapshots**: A es fuente de escritura y una
función de refresco lee su catálogo y actualiza B/C en una transacción por réplica,
con una versión guardada. El refresco es explícito y asíncrono; no es replicación
lógica nativa, streaming ni consenso. Un lector puede observar la versión anterior
hasta que se complete el refresco. Las versiones identifican snapshots publicados;
A puede contener cambios aún no publicados con el número de versión anterior.

El costo es apropiado para 1.000 productos y un catálogo poco mutable. Se debe
probar: cambio confirmado en A, lectura todavía antigua en B/C, refresco y
coincidencia de precio/versión. La copia local permite leer catálogos cuando otro
nodo está indisponible. Los fragmentos de pedidos no se replican; perder su nodo
impide consultar ese fragmento. No hay promoción automática ni elección de líder.

## Índices y planes

B-tree mantiene las PK y constituye la alternativa dinámica para el índice de
cliente. ISAM permite observar el costo del directorio estático con claves
repetidas y acceso al heap. Sin índice secundario permite medir el acceso
secuencial cuando no hay una alternativa selectiva. Los planes normales deben
registrarse con `EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON)`; un plan forzado para
comprobar capacidades se identifica como diagnóstico y no como plan del benchmark.
Los índices son locales a cada fragmento: los TIDs solo identifican tuplas del
heap de su nodo. FDW transmite consultas y valores, no TIDs globales ni páginas
de un índice compartido. El coste de FDW, el resultado y la latencia pueden dominar diferencias pequeñas
entre índices.

## Latencia y transferencia

La rúbrica fija A–B=20 ms, A–C=40 ms y B–C=25 ms. El experimento interpreta estos
valores como un coste de ida y vuelta por enlace lógico utilizado y lo **simula
en el cliente** antes de ejecutar cada operación. Se conservan por separado la
espera modelada, la duración de la consulta real y el tiempo completo. El control
`base` añade cero espera; `model` utiliza la matriz indicada.

Esta aproximación no cambia el transporte de Docker, no aplica `netem`, no modela
ancho de banda, congestión, reintentos ni todas las rondas del protocolo FDW. Los
enlaces lógicos se computan de forma explícita según origen y destinos; no se
interpreta la suma de esperas como una medición física de latencia entre máquinas.

La transferencia se registra mediante diferencias de contadores RX/TX de `eth0`
de cada contenedor durante el tramo medido. Incluye clientes, FDW y protocolo;
no son exclusivamente bytes de filas útiles. Sumar RX y TX cuenta ambos extremos
de ciertas transferencias. El tamaño serializado del resultado es una medida
lógica adicional y se mantiene separado.

## Contrato de validación antes de experimentar

1. Las cuatro relaciones existen en los tres nodos y las FK locales son válidas.
2. La suma de pedidos y detalles propietarios es N; no hay duplicados globales.
3. Cada pedido satisface el predicado de su propietario y su cliente/región.
4. Las sumas y huellas de contenido coinciden con una referencia determinista y
   entre estrategias; las vistas FDW reconstruyen esos resultados.
5. El snapshot de productos muestra divergencia antes del refresco y convergencia
   después. Las versiones permiten identificar el estado observado.
6. La caída de C conserva consultas locales A/B y catálogos replicados; las
   consultas que necesitan el fragmento C fallan de forma visible, sin devolver
   silenciosamente un total parcial. Tras reiniciar, se comprueba recuperación.
7. La carga contiene exactamente 70 lecturas y 30 escrituras por cada 100
   operaciones; los perfiles equilibrado y concentrado conservan la misma
   secuencia entre estrategias/índices. Cada medición oficial se repite cinco veces.
8. Toda salida oficial registra N, semillas, versión, parámetros, estado de
   terminación, fallos, duración y procedencia. Un diagnóstico pequeño queda
   etiquetado como `smoke` y no sustituye los resultados oficiales.

El bloque 7 queda especificado mediante este contrato. El cumplimiento observado
del bloque 8 debe acreditarse con los archivos de validación y resultados; el
diseño por sí solo no prueba que una ejecución haya pasado.
