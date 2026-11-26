# Spec 01 — Reglas de negocio

Fuente de verdad ejecutable: cada regla `R*` tiene al menos un test con su ID en el nombre
(`test_R4_...`). Si una regla cambia, cambia primero este documento y luego el test.

## Modelo

**Evento** (entrada):
`event_id` (str, único, obligatorio), `delivery_id`, `merchant_id`, `courier_id`,
`type` ∈ {creada, asignada, recogida, en_ruta, entregada, fallida},
`occurred_at` (ISO-8601 con offset; se normaliza a UTC), `lat`/`lon` (obligatorios en `recogida` y `entregada`).

**Comercio** (config): `id`, `name`, `timezone` (IANA), `base_fee_cents`, `per_km_cents`, `notes` (texto NO confiable).

**Entrega** (estado derivado, recalculable desde sus eventos): `status`, `cost_cents | null`,
`cost_status` ∈ {calculado, pendiente}, `breakdown` (desglose auditable), `anomalies[]`.

## Reglas

| ID | Regla | Dado / Cuando / Entonces |
|---|---|---|
| R1 | Ciclo de estados | Orden: creada < asignada < recogida < en_ruta < entregada. El estado de una entrega es el **más avanzado** por orden de ciclo, no el último en llegar. |
| R2 | Fallida | Puede ocurrir desde cualquier estado previo a `entregada`. Estado = `fallida` si existe `fallida` y no existe `entregada`. |
| R3 | Costo entrega exitosa | `base + km × per_km + recargo_nocturno`. Todo en centavos enteros. |
| R4 | Distancia | Haversine (radio 6371.0088 km) entre `recogida` y `entregada`. La distancia se redondea a 3 decimales (metros) para que el cálculo sea reproducible y auditable; el recargo = km × `per_km_cents` se redondea half-up al centavo. |
| R5 | Recargo nocturno | 15% de `(base + recargo_distancia)` si la hora local del comercio de `occurred_at` de `entregada` ∈ [20:00, 06:00). 20:00:00 es nocturno; 06:00:00 no lo es. La zona se aplica con `zoneinfo` (maneja DST). |
| R6 | Fallida cobra 40% | Entrega `fallida`: costo = 40% de `base`, **sin** distancia ni recargo. No requiere coordenadas. |
| R7 | Idempotencia | Mismo `event_id` con mismo contenido → 200 `{duplicate: true}`, sin efectos. Mismo `event_id` con contenido distinto → 409 y no se modifica nada. |
| R8 | Orden de llegada irrelevante | El costo se recalcula sobre el **conjunto** de eventos. Cualquier permutación de los mismos eventos produce el mismo costo y estado. |
| R9 | Costo pendiente | Si hay `entregada` pero falta `recogida` (o viceversa sin `entregada`), `cost_status=pendiente`, `cost_cents=null`. Se completa al llegar el evento faltante. |
| R10 | `fallida` tardía | Si existe `entregada`, un `fallida` posterior/contradictorio **no cambia** estado ni costo; se registra en `anomalies[]`. |
| R11 | Zona horaria | Cada comercio tiene su `timezone`; R5 usa esa zona, nunca la del servidor. |
| R12 | Trazabilidad | Cada costo guarda `breakdown`: base, km, per_km, recargo_distancia, recargo_nocturno, % aplicados, tarifa usada, `event_ids` usados, versión del algoritmo. |

## Supuestos documentados (ambigüedades del enunciado)

- **S1** Recargo nocturno = 15% sobre base + distancia (el enunciado no dice sobre qué base).
- **S2** Dinero en centavos enteros; redondeo half-up al centavo; nunca `float` en el monto.
- **S3** Distancia en línea recta (Haversine), no por rutas reales.
- **S4** Para rangos de fecha se usa el instante de cierre de la entrega (`entregada` o `fallida`) en UTC, intervalo `[desde, hasta)`.
- **S5** Tarifas fijas por comercio (sin versionado histórico); el desglose guarda la tarifa usada en el momento del cálculo.
- **S6** Eventos sin `event_id` se rechazan (422); el emisor es responsable de la idempotencia.
- **S7** Si los eventos de un mismo `delivery_id` traen distinto `merchant_id` o `courier_id` → 409 (inconsistencia). La reasignación de mensajero queda fuera de alcance.
- **S8** Si hay dos eventos del mismo tipo con distinto `event_id` (no son duplicados), se usa de forma determinista el de menor `(occurred_at, event_id)` y el otro se registra en `anomalies[]`.
- **S9** `address` es opcional en cualquier evento y solo sirve para el buscador; la entrega usa la del evento más temprano que la traiga. No participa en el costo.
- **S10** Moneda única del servicio: **COP**. Los montos son enteros en centavos (unidad menor, ISO 4217; `*_cents`), sin conversión entre monedas. Los comercios de otras zonas horarias del dataset existen para ejercitar R11, no implican otra moneda. Las respuestas incluyen `currency: "COP"`.
- **S11** `merchant-totals` cuenta entregas con costo calculado (entregadas + fallidas) cerradas en el rango; las entregadas sin recogida (costo pendiente) se reportan aparte en `pending_cost_deliveries`, nunca se suman ni se ocultan.
