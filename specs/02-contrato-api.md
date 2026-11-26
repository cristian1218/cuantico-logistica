# Spec 02 — Contrato de API

Base: `/api`. Autenticación: header `Authorization: Bearer <token>` (ver Spec 03). `/api/health` es público.

| Método | Ruta | Descripción | Respuestas |
|---|---|---|---|
| POST | `/api/events` | Ingesta de un evento (R7, R8) | 201 creado · 200 `{duplicate:true}` · 401 · 403 · 409 conflicto · 422 inválido |
| GET | `/api/deliveries/{id}` | Entrega con estado, costo y desglose (R12) | 200 · 401 · 404 (inexistente **o fuera de alcance**) |
| GET | `/api/reports/merchant-totals?merchant_id&from&to` | Total facturado y nº de entregas de un comercio en `[from, to)` (S4, S11) | 200 · 401 · 403 · 404 · 422 |
| GET | `/api/reports/courier-status?courier_id` | Nº de entregas por estado de un mensajero, **limitado al alcance del usuario** | 200 · 401 |
| GET | `/api/deliveries/search?q=` | Buscador de texto libre (1–100 car.), parametrizado (SEC1). Máx. 50 resultados, nunca devuelve notas | 200 · 401 · 422 |
| POST | `/api/chat` | `{message}` → `{answer, tool_calls:[{name,args,result}]}` (fase 4) | 200 · 4xx/5xx con `{error}` |
| GET | `/api/health` | Liveness | 200 |

## Evento de entrada

```json
{ "event_id": "str", "delivery_id": "str", "merchant_id": "str", "courier_id": "str",
  "type": "creada|asignada|recogida|en_ruta|entregada|fallida",
  "occurred_at": "ISO-8601 CON zona horaria", "lat": 0.0, "lon": 0.0, "address": "opcional" }
```
Ids de 1–64 caracteres. `lat/lon` obligatorios en `recogida` y `entregada`. Campos desconocidos → 422 (`extra=forbid`).

## Errores

Siempre `{error: {code, message}}` (+ `details[{field,message}]` en 422). Nunca trazas ni valores recibidos. Los 500 devuelven un mensaje genérico; el detalle va solo al log del servidor.

| Código | HTTP | Cuándo |
|---|---|---|
| `unauthorized` | 401 | token ausente o inválido |
| `forbidden` | 403 | comercio fuera del alcance del token |
| `not_found` | 404 | no existe, o existe pero fuera de alcance (no se revela, evita enumeración) |
| `conflicting_event` | 409 | R7: mismo `event_id`, contenido distinto |
| `inconsistent_events` | 409 | S7 |
| `validation_error` / `unknown_merchant` | 422 | payload inválido / comercio inexistente |
| `internal_error` | 500 | error no controlado |

El campo `tool_calls` del chat permite al frontend mostrar **los datos consultados** (requisito de la prueba).
