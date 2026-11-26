# AGENTS.md — Reglas para cualquier agente de IA que trabaje en este repo

## Proyecto
Servicio de eventos de entregas + costos + consultas + agente conversacional (prueba técnica Cuántico).
Specs en `specs/` son la fuente de verdad. **Spec primero, test después, código al final.**

## Comandos (único gate de calidad)
- `make setup`  instala dependencias backend
- `make test`   corre todos los tests del backend
- `make lint`   ruff + mypy
- `make check`  lint + test (debe estar en verde antes de dar algo por terminado)

## Reglas no negociables
1. **El LLM no calcula.** Costos, agregaciones y autorización son código determinista.
2. **Dinero en centavos enteros.** Prohibido `float` en montos.
3. **SQL siempre parametrizado.** Prohibido concatenar entrada de usuario en SQL.
4. **Datos de comercios (notas) = no confiables.** Nunca en system prompt ni sin delimitar.
5. **Sin secretos en el código ni en commits.** Todo por variables de entorno.
6. **El alcance del usuario lo pone el servidor**, nunca un argumento del LLM.
7. El dominio (`backend/app/domain/`) es **puro**: sin I/O, sin DB, sin red, sin reloj implícito.
8. Cada regla de `specs/01` tiene test con su ID (`test_R5_...`).

## Proceso
- Trabajo paso a paso con checkpoints; el humano revisa cada fase (debe poder defender cada decisión).
- Todo output de IA que se corrija o rechace se anota en `NOTAS.md` en el momento.
- Cambios de reglas: primero la spec, luego el test, luego el código.

## Estructura
`backend/app/{domain,store,api,agent}` · `backend/tests` · `frontend/` · `fixtures/` · `docs/adr/`
