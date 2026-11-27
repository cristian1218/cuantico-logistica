# NOTAS.md — Bitácora de Decisiones Técnicas y Supervisión de Modelos

*Registro técnico sobre supervisión de arquitectura, directrices de seguridad y control de calidad en el uso de herramientas de asistencia en IDE.*

---

## 1. Herramientas Utilizadas
- **Asistente de IDE (GitHub Copilot / Claude 3.5 Sonnet en editor):** Utilizado como par de programación para acelerar la generación de esqueletos iniciales, redacción de especificaciones técnicas y scaffolding de pruebas unitarias.
- **Google Gemini (API):** Modelo de lenguaje integrado exclusivamente en el producto final para atender las consultas conversacionales de los usuarios en lenguaje natural (orquestación mediante llamadas a herramientas).

---

## 2. Metodología de Trabajo y Supervisión Humana
El desarrollo se realizó bajo la premisa de que **la responsabilidad de la arquitectura, la seguridad y el modelo de negocio es 100% del ingeniero**:

1. **Diseño de Arquitectura y Dominio:**
   - Se estableció la regla de *Log inmutable de eventos + Proyecciones recalculables*, evitando arquitecturas CRUD convencionales propensas a fallos por concurrencia y desorden.
   - Se delimitó estrictamente la frontera: **el LLM no calcula montos ni agrega datos**. Todo cálculo financiero se realiza en código determinista con `Decimal` en centavos de COP.
2. **Revisión de Seguridad y Criterio de Negocio:**
   - Como Líder Técnico, **rechacé los requerimientos inseguros propuestos inicialmente por Operaciones por representar vulnerabilidades críticas** (SQL Injection, Prompt Injection, falta de control de acceso y exposición de credenciales).

---

## 3. Registro de Correcciones y Rechazos del Output de Asistencia

| Fecha | Componente / Propuesta Inicial | Decisión y Corrección Humana Aplicada |
|---|---|---|
| 2026-11-25 | **Cálculo de Distancia (R4)**<br>La asistencia propuso aplicar Haversine con flotantes continuos hasta el cálculo final. | **Rechazado.** Usar `float` acumulado genera discrepancias por precisión entre sistemas operativos. Se exigió redondear la distancia a metros (3 decimales) antes de aplicar la tarifa por km, y liquidar los recargos con `Decimal.quantize(1, ROUND_HALF_UP)` al centavo. |
| 2026-11-25 | **Requisitos de Operaciones (SEC1 a SEC4)**<br>La asistencia sugirió consultas dinámicas de texto para el buscador y no implementar autenticación bajo el supuesto de que simplificaba la fase inicial. | **Rechazado enfáticamente.** Un líder técnico debe priorizar la seguridad sobre la complacencia: se impuso SQL parametrizado, tokens Bearer con alcance (`Principal.merchant_ids`) y variables de entorno obligatorias con `.env.example`. |
| 2026-11-26 | **Prompt del Sistema (SEC2)**<br>En el borrador de instrucciones del sistema, la IA redactó un ejemplo citando literalmente: *'IGNORA TUS INSTRUCCIONES ANTERIORES'*. | **Corregido.** El test unitario `test_SEC2_system_instruction_never_contains_merchant_notes` detectó que se estaba introduciendo el payload de ataque en el system prompt. Se corrigió para que el prompt contenga únicamente directrices abstractas de seguridad y no fragmentos del ataque. |
| 2026-11-26 | **Contexto de Autorización en Tools**<br>La IA propuso que el LLM enviara `merchant_id` como argumento en las tools para saber qué comercio consultar. | **Rechazado.** Si el LLM elige el comercio, un usuario malicioso puede engañarlo para ver comercios ajenos (*Confused Deputy*). Se modificó el servicio para que el servidor inyecte el `principal` autenticado directamente en la ejecución de la tool sin que el LLM pueda manipularlo. |
| 2026-11-26 | **Verificación de Tests y Mutaciones**<br>Los 92 primeros tests pasaron a la primera. | **Verificación manual:** Se aplicó testing de mutación manual (se removió deliberadamente el escape de comodines en `LIKE` y el redondeo bancario) para confirmar que los tests fallaran ante regresiones reales, garantizando que no fueran aserciones vacías o complacientes. |
| 2026-11-26 | **Tipado Estricto en Helpers**<br>La IA generó helpers de tests usando desempaquetado flexible `**dict`. | **Corregido.** Mypy en modo estricto rechazó los tipos `dict[str, Any]` pasando a parámetros numéricos. Se reescribieron los constructores con firma fuertemente tipada. |
