# ADR 0001: Escalado a 10.000 ev/s y Auditoría de Costos de Entrega

- **Estado:** Propuesto / Aceptado
- **Fecha:** 2026-11-26
- **Contexto:** El servicio pasa de 5 a 50 comercios y de cientos a 10.000 eventos por segundo. El área de operaciones exige trazabilidad y auditoría exacta de cómo se calculó cada costo.

---

## 1. Problema y Fuerzas en Conflicto

1. **Rendimiento y Concurrencia:** A 10.000 ev/s, una base de datos relacional con bloqueos transaccionales por entrega (`BEGIN IMMEDIATE` / `SELECT FOR UPDATE`) colapsa por contención de I/O y bloqueo de filas.
2. **Desorden e Idempotencia:** Los eventos llegan con reintentos y fuera de orden. El cálculo no puede depender del orden de llegada.
3. **Auditoría Estricta:** Se requiere explicar retrospectivamente cualquier cobro: qué tarifa regía, coordenadas exactas, distancia calculada, recargo nocturno aplicado y eventos involucrados.
4. **Costo Operacional:** Mantener el sistema gobernable sin sobreingeniería excesiva.

---

## 2. Opciones Evaluadas

### Opción A: Escalamiento Vertical en PostgreSQL con Escritura Síncrona
- **Descripción:** Mismo diseño relacional sobre una instancia PostgreSQL de alta gama (64 vCPU, NVMe).
- **Ventajas:** Consistencia inmediata (ACID estricto); sin sistemas distribuidos adicionales.
- **Desventajas:** Cuello de botella en bloqueos de fila ante ráfagas concurrentes de una misma entrega; límite físico de escalabilidad horizontal; I/O saturado a 10k escrituras/segundo sin buffer.

### Opción B: Log de Eventos Particionado (Kafka/Redpanda) + Workers Deterministas + Proyecciones CQRS (Elegida)
- **Descripción:**
  - **Ingesta:** API Gateway / microservicio de ingesta rápido (Go/Rust/FastAPI) que valida esquema básico y publica a Kafka particionando por `delivery_id` como clave (`key=delivery_id`).
  - **Procesamiento:** Grupo de workers que consumen la partición. Dado que todos los eventos de la entrega `d` van a la misma partición y consumidor, **se elimina la concurrencia competitiva sobre una misma entrega sin bloqueos distribuidos**.
  - **Cálculo:** El worker ejecuta la función pura de dominio `compute_delivery(events, tariff)` y actualiza la tabla de lectura (PostgreSQL / ClickHouse).
  - **Auditoría:** Cada recálculo genera un registro inmutable `cost_audit_log` con: `breakdown` (base, km, per_km, recargo nocturno), versión del algoritmo, hash de los eventos usados y snapshot inmutable de la tarifa del comercio al momento del cálculo.
- **Ventajas:** Absorbe picos de 10k ev/s en memoria/disco secuencial; preserva idempotencia y desorden sin contención; auditoría nativa por diseño event-driven.
- **Desventajas:** Consistencia eventual (latencia P99 de 50–200 ms entre ingesta y consulta agregada); complejidad de operar un cluster de Kafka.

### Opción C: Cola Simple sin Partición (AWS SQS / RabbitMQ) + Redis Locks
- **Descripción:** Workers toman eventos aleatorios y adquieren un cerrojo distribuido (Redlock) por `delivery_id`.
- **Desventajas:** Alto riesgo de *lock contention*, sobrecarga de red por cerrojos y riesgo de carreras si expira el TTL del lock. Descartada.

---

## 3. Decisión y Arquitectura Seleccionada

Se adopta la **Opción B (Log Particionado + CQRS + Auditoría Snapshot)**.

1. **Partición por `delivery_id`:** Garantiza procesamiento serial por entrega sin necesidad de bloqueos distribuidos.
2. **Snapshot Inmutable de Tarifa:** La tarifa del comercio se versiona (`tariff_version_id`). El cálculo auditable guarda la versión aplicada; si el comercio sube precios hoy, los cobros pasados no se alteran.
3. **Event Store Append-Only:** Los eventos nunca se mutan ni eliminan; se almacenan en almacenamiento de objetos / tabla columnar para auditoría fiscal.

---

## 4. Trade-offs Asumidos

| Beneficio Obtenido | Concesión Aceptada (Trade-off) | Mitigación |
|---|---|---|
| Alto rendimiento (10k+ ev/s sin bloqueos) | Consistencia eventual en consultas | Notificaciones WebSocket al frontend para entregas cerradas; latencia P99 < 150ms |
| Trazabilidad absoluta de centavos | Mayor volumen de almacenamiento por desgloses | Políticas de retención tiered: 90 días en DB activa, histórico a S3/Parquet |
| Resiliencia ante caídas de workers | Complejidad de infraestructura (Kafka + DB) | Uso de alternativas ligeras como Redpanda o servicios administrados (AWS MSK) |
