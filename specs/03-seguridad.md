# Spec 03 — Seguridad y respuesta a los requisitos de Operaciones

Cada requisito de Operaciones se evaluó; los 4 introducen riesgo y se resuelven distinto a lo pedido.

| ID | Pedido por Operaciones | Riesgo | Decisión | Test |
|---|---|---|---|---|
| SEC1 | Buscador concatenando texto en SQL | SQL injection | Consultas parametrizadas; `%`, `_` y `\` del usuario se escapan en `LIKE`; `LIMIT 50`; longitud máx. de `q` | `test_SEC1_*` |
| SEC2 | Notas del comercio "tal cual" en el prompt | Prompt injection indirecta (el dataset incluye el payload) | Las notas son **dato no confiable**: nunca en system prompt; solo accesibles vía tool `get_merchant_info`, devueltas como dato delimitado/etiquetado, truncadas y con caracteres de control removidos. Aunque el modelo "obedezca", no existe tool con alcance global | `test_SEC2_*` + eval |
| SEC3 | Sin control de acceso | Fuga entre comercios/mensajeros; el agente como *confused deputy* | Token por usuario con **alcance** (`merchant_ids` o `all`). El alcance se inyecta en las tools desde el **servidor**, nunca desde argumentos del LLM. Sin token → 401. Recurso de otro comercio: 403 en operaciones explícitas sobre un comercio (ingesta, totales); 404 en lectura por id (no revela existencia); consultas por mensajero y buscador se **filtran** al alcance. Tokens comparados en tiempo constante | `test_SEC3_*` |
| SEC4 | Credenciales en el código | Fuga de secretos | Variables de entorno (`.env` ignorado por git, `.env.example` versionado). Falla al arrancar con mensaje claro si falta algo obligatorio; mock de LLM si no hay key | `test_SEC4_*` |

## Frontera determinista / LLM

- **Determinista:** validación, cálculo de costos, agregaciones, autorización, filtrado de datos.
- **LLM:** elegir qué tool llamar, extraer argumentos del lenguaje natural, redactar la respuesta con los resultados.
- El LLM **no calcula** ni ve datos fuera del alcance del usuario. Sus argumentos se validan con esquemas estrictos.
- Si se pide "más libertad al modelo": la respuesta es que la libertad se amplía añadiendo tools deterministas nuevas, no quitando restricciones.

## Mínimo aceptado en esta prueba (y qué sería con una semana)

Tokens estáticos con alcance (en `.env`) → con una semana: OIDC/JWT, roles, auditoría de consultas del agente, rate limiting, *red teaming* continuo.
