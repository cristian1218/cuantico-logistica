"""Calculo de costos y estado de una entrega.

Funcion pura: `compute_delivery(eventos, tarifa)` depende solo del CONJUNTO de eventos,
nunca del orden de llegada (R8) ni de duplicados (R7). El estado se recalcula entero
cada vez; asi la idempotencia, el desorden y la auditoria salen del mismo mecanismo.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import time
from decimal import ROUND_HALF_UP, Decimal
from zoneinfo import ZoneInfo

from app.domain.errors import ConflictingEventError, InconsistentEventsError
from app.domain.geo import haversine_km
from app.domain.models import (
    LIFECYCLE_ORDER,
    CostBreakdown,
    DeliveryState,
    Event,
    EventType,
    Tariff,
)

ALGORITHM_VERSION = "1.0"
NIGHT_SURCHARGE_PERCENT = 15  # R5
FAILED_PERCENT = 40  # R6
NIGHT_START = time(20, 0)  # R5: [20:00, 06:00)
NIGHT_END = time(6, 0)


def _percent_of(amount_cents: int, percent: int) -> int:
    """S2: porcentaje en enteros, redondeo half-up al centavo. Sin float."""
    value = Decimal(amount_cents) * Decimal(percent) / Decimal(100)
    return int(value.quantize(Decimal(1), rounding=ROUND_HALF_UP))


def _distance_charge_cents(distance_km: float, per_km_cents: int) -> int:
    # distance_km ya viene redondeado a 3 decimales; str() evita arrastrar ruido binario.
    value = Decimal(str(distance_km)) * Decimal(per_km_cents)
    return int(value.quantize(Decimal(1), rounding=ROUND_HALF_UP))


def is_night(local_time: time) -> bool:
    return local_time >= NIGHT_START or local_time < NIGHT_END


def dedupe_events(events: Iterable[Event]) -> list[Event]:
    """R7: elimina duplicados exactos; mismo id con contenido distinto es conflicto."""
    seen: dict[str, Event] = {}
    for event in events:
        previous = seen.get(event.event_id)
        if previous is None:
            seen[event.event_id] = event
        elif previous != event:
            raise ConflictingEventError(
                f"event_id '{event.event_id}' reutilizado con contenido distinto"
            )
    return list(seen.values())


def _check_consistency(events: list[Event]) -> None:
    first = events[0]
    for e in events:
        if (e.delivery_id, e.merchant_id, e.courier_id) != (
            first.delivery_id,
            first.merchant_id,
            first.courier_id,
        ):
            raise InconsistentEventsError(
                f"eventos con delivery/merchant/courier distintos en '{first.delivery_id}'"
            )


def _pick_per_type(events: list[Event]) -> tuple[dict[EventType, Event], list[str]]:
    """S8: por tipo, se usa de forma determinista el menor (occurred_at, event_id)."""
    by_type: dict[EventType, list[Event]] = {}
    for e in events:
        by_type.setdefault(e.type, []).append(e)
    chosen: dict[EventType, Event] = {}
    anomalies: list[str] = []
    for etype, group in by_type.items():
        group.sort(key=lambda e: (e.occurred_at, e.event_id))
        chosen[etype] = group[0]
        if len(group) > 1:
            ignored = ", ".join(e.event_id for e in group[1:])
            anomalies.append(
                f"multiples eventos '{etype.value}': se uso {group[0].event_id}, ignorados {ignored}"
            )
    return chosen, anomalies


def _status(chosen: dict[EventType, Event]) -> EventType:
    if EventType.ENTREGADA in chosen:
        return EventType.ENTREGADA  # R2: una vez entregada, es entregada
    if EventType.FALLIDA in chosen:
        return EventType.FALLIDA  # R2
    # R1: el mas avanzado del ciclo, no el ultimo en llegar
    for etype in reversed(LIFECYCLE_ORDER):
        if etype in chosen:
            return etype
    raise ValueError("sin eventos")  # inalcanzable: se valida antes


def compute_delivery(events: Iterable[Event], tariff: Tariff) -> DeliveryState:
    unique = dedupe_events(events)
    if not unique:
        raise ValueError("se requiere al menos un evento")
    _check_consistency(unique)
    chosen, anomalies = _pick_per_type(unique)
    status = _status(chosen)
    first = unique[0]

    breakdown: CostBreakdown | None = None
    closed_at = None

    if status == EventType.ENTREGADA:
        delivered = chosen[EventType.ENTREGADA]
        closed_at = delivered.occurred_at
        pickup = chosen.get(EventType.RECOGIDA)
        if EventType.FALLIDA in chosen:  # R10
            anomalies.append(
                f"fallida ({chosen[EventType.FALLIDA].event_id}) recibida con entrega "
                "ya entregada: ignorada"
            )
        if pickup is not None:  # R9: sin recogida, el costo queda pendiente
            assert pickup.lat is not None and pickup.lon is not None
            assert delivered.lat is not None and delivered.lon is not None
            km = haversine_km(pickup.lat, pickup.lon, delivered.lat, delivered.lon)  # R4
            distance_charge = _distance_charge_cents(km, tariff.per_km_cents)
            local = delivered.occurred_at.astimezone(ZoneInfo(tariff.timezone))  # R11
            night = _percent_of(
                tariff.base_fee_cents + distance_charge, NIGHT_SURCHARGE_PERCENT
            )  # S1
            surcharge = night if is_night(local.time()) else 0  # R5
            total = tariff.base_fee_cents + distance_charge + surcharge  # R3
            breakdown = CostBreakdown(
                outcome="entregada",
                base_fee_cents=tariff.base_fee_cents,
                per_km_cents=tariff.per_km_cents,
                timezone=tariff.timezone,
                distance_km=km,
                distance_charge_cents=distance_charge,
                night_surcharge_percent=NIGHT_SURCHARGE_PERCENT,
                night_surcharge_cents=surcharge,
                failed_percent=None,
                local_delivery_time=local.isoformat(),
                total_cents=total,
                event_ids_used=tuple(sorted((pickup.event_id, delivered.event_id))),
                algorithm_version=ALGORITHM_VERSION,
            )
    elif status == EventType.FALLIDA:
        failed = chosen[EventType.FALLIDA]
        closed_at = failed.occurred_at
        total = _percent_of(tariff.base_fee_cents, FAILED_PERCENT)  # R6
        breakdown = CostBreakdown(
            outcome="fallida",
            base_fee_cents=tariff.base_fee_cents,
            per_km_cents=tariff.per_km_cents,
            timezone=tariff.timezone,
            distance_km=None,
            distance_charge_cents=0,
            night_surcharge_percent=0,
            night_surcharge_cents=0,
            failed_percent=FAILED_PERCENT,
            local_delivery_time=None,
            total_cents=total,
            event_ids_used=(failed.event_id,),
            algorithm_version=ALGORITHM_VERSION,
        )

    return DeliveryState(
        delivery_id=first.delivery_id,
        merchant_id=first.merchant_id,
        courier_id=first.courier_id,
        status=status,
        cost_status="calculado" if breakdown else "pendiente",
        cost_cents=breakdown.total_cents if breakdown else None,
        breakdown=breakdown,
        closed_at=closed_at,
        anomalies=tuple(sorted(anomalies)),
    )
