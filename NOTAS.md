# NOTAS.md — Uso de herramientas de IA (registro transparente)

Se actualiza **durante** el trabajo, no al final.

## Herramientas
- Asistente de IA agéntico (Antigravity / Claude Sonnet) como par de programación: análisis de la prueba, redacción de specs, scaffolding, generación de tests y código bajo revisión humana.
- Gemini (API) como LLM del agente conversacional del producto (no como herramienta de desarrollo).

## Cómo se usó
| Fase | Para qué | Quién decidió |
|---|---|---|
| 0 | Análisis del enunciado, identificación de trampas en requisitos de Operaciones | IA propuso, humano aprobó |
| 1 | Specs 01–03, AGENTS.md, Makefile | IA propuso, humano aprobó (supuestos S1–S7 pendientes de revisión fina) |

## Correcciones y rechazos del output de IA
_(se llena a medida que ocurren)_

| Fecha | Qué generó la IA | Qué se corrigió/rechazó y por qué |
|---|---|---|
| 2026-11-25 | Spec R4 original: Haversine "sin redondeo intermedio" | Ambigua y no reproducible (float entre plataformas). Se cambió a distancia redondeada a metros (3 decimales) antes de multiplicar; se añadió S8 (dos eventos del mismo tipo) al diseñar los tests |
| 2026-11-26 | Dominio + 31 tests escritos en rojo primero (TDD) y luego implementación | Primer `make check` falló por reglas de estilo de ruff (alias `datetime.UTC`, `if` anidados); se corrigió. Los tests de lógica pasaron a la primera, así que se revisaron a mano los valores esperados (16120, 18538) contra el cálculo manual, no solo contra la salida del código |
| 2026-11-26 | API + persistencia + buscador + auth: 61 tests en rojo y luego implementación (92 en total) | Pasaron a la primera, lo que levantó sospecha de tests débiles. Se hizo una **mutación manual** (quitar el escape de `LIKE`) y `test_SEC1_percent_and_underscore_are_literals` falló como debía. Hallazgo: los payloads de inyección clásicos (`' OR 1=1`) pasan incluso sin escape porque los parámetros enlazados ya los neutralizan; el escape protege contra comodines `%`/`_`, que es otro problema (búsquedas que devuelven todo). Ambos se testean por separado |
| 2026-11-26 | Helper de tests con `**dict` | mypy strict lo rechazó (`**dict[str,str]` hacia parámetros `float`); se reescribió con argumentos explícitos |
| 2026-11-26 | Requisito de Operaciones: buscador con SQL concatenado; sin control de acceso; credenciales en código | **Rechazados** (SEC1, SEC3, SEC4): consultas parametrizadas, tokens con alcance y secretos por entorno. Detalle en `specs/03-seguridad.md` |
| 2026-11-26 | Agente conversacional + Tools + SEC2 (13 tests nuevos, 105 en total) | En el borrador inicial de `SYSTEM_INSTRUCTION` se incluyó `(ej. 'IGNORA TUS INSTRUCCIONES ANTERIORES')` como ejemplo de lo que no debía obedecer. El test de seguridad `test_SEC2_system_instruction_never_contains_merchant_notes` lo detectó y falló de inmediato: el system prompt no debe contener fragmentos del payload de ataque. Se reemplazó por una descripción genérica de comandos de evasión |
| 2026-11-26 | Inyección del contexto de autorización en tools | El LLM no puede pasar `principal` como argumento de tool. El servidor lo inyecta directamente desde la autenticación del usuario. Si un usuario acotado pregunta por otro comercio, la tool retorna error de autorización antes de tocar la base de datos |
