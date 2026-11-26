"""Tests del dominio puro. Cada test lleva el ID de la regla en specs/01-reglas-negocio.md.

Datos de referencia (calculados a mano):
- (0,0) -> (1,0) = 1 grado de latitud = 111.195 km con radio 6371.0088.
- base 5000, per_km 100 -> distancia 111.195 * 100 = 11119.5 -> half-up 11120. Total diurno = 16120.
- Nocturno: 15% de 16120 = 2418 -> total 18538.
"""

from __future__ import annotations

import itertools
from datetime import UTC, datetime

import pytest
from hypothesis import given
from hypothesis import strategies as st

from app.domain.costing import compute_delivery, dedupe_events
from app.domain.errors import ConflictingEventError, InconsistentEventsError
from app.domain.geo import haversine_km
from app.domain.models import Event, EventType, Tariff

BOGOTA = Tariff(base_fee_cents=5000, per_km_cents=100, timezone="America/Bogota")


def utc(y: int, mo: int, d: int, h: int, mi: int = 0, s: int = 0) -> datetime:
    return datetime(y, mo, d, h, mi, s, tzinfo=UTC)


def ev(
    eid: str,
    etype: EventType,
    at: datetime,
    lat: float | None = None,
    lon: float | None = None,
    delivery: str = "d1",
    merchant: str = "m1",
    courier: str = "c1",
) -> Event:
    return Event(
        event_id=eid,
        delivery_id=delivery,
        merchant_id=merchant,
        courier_id=courier,
        type=etype,
        occurred_at=at,
        lat=lat,
        lon=lon,
    )


# 14:00 UTC = 09:00 Bogota (diurno)
DAY = utc(2025, 3, 10, 14, 0)


def happy_events(delivered_at: datetime = DAY) -> list[Event]:
    return [
        ev("e1", EventType.CREADA, utc(2025, 3, 10, 12)),
        ev("e2", EventType.ASIGNADA, utc(2025, 3, 10, 12, 5)),
        ev("e3", EventType.RECOGIDA, utc(2025, 3, 10, 12, 30), 0.0, 0.0),
        ev("e4", EventType.EN_RUTA, utc(2025, 3, 10, 12, 40)),
        ev("e5", EventType.ENTREGADA, delivered_at, 1.0, 0.0),
    ]


# ---------- geo ----------
def test_R4_haversine_one_degree_latitude() -> None:
    assert haversine_km(0.0, 0.0, 1.0, 0.0) == 111.195


def test_R4_haversine_same_point_is_zero() -> None:
    assert haversine_km(4.6, -74.1, 4.6, -74.1) == 0.0


# ---------- R1 / R2: estados ----------
def test_R1_status_is_most_advanced_not_last_arrived() -> None:
    events = [
        ev("e5", EventType.ENTREGADA, DAY, 1.0, 0.0),
        ev("e1", EventType.CREADA, utc(2025, 3, 10, 12)),
    ]
    assert compute_delivery(events, BOGOTA).status == EventType.ENTREGADA


def test_R1_in_progress_status_and_cost_pending() -> None:
    state = compute_delivery(happy_events()[:4], BOGOTA)
    assert state.status == EventType.EN_RUTA
    assert state.cost_cents is None
    assert state.cost_status == "pendiente"


def test_R2_failed_before_delivery_is_failed_status() -> None:
    events = [
        ev("e1", EventType.CREADA, utc(2025, 3, 10, 12)),
        ev("e2", EventType.FALLIDA, utc(2025, 3, 10, 13)),
    ]
    assert compute_delivery(events, BOGOTA).status == EventType.FALLIDA


# ---------- R3 / R4: costo ----------
def test_R3_R4_daytime_cost_with_half_up_rounding() -> None:
    state = compute_delivery(happy_events(), BOGOTA)
    assert state.cost_status == "calculado"
    assert state.cost_cents == 16120  # 5000 + round_half_up(11119.5)=11120
    assert state.breakdown is not None
    assert state.breakdown.distance_km == 111.195
    assert state.breakdown.distance_charge_cents == 11120
    assert state.breakdown.night_surcharge_cents == 0


def test_R3_cost_is_integer_cents() -> None:
    assert isinstance(compute_delivery(happy_events(), BOGOTA).cost_cents, int)


# ---------- R5 / R11: nocturno y zonas ----------
@pytest.mark.parametrize(
    ("utc_time", "night"),
    [
        (utc(2025, 3, 11, 0, 59, 59), False),  # 19:59:59 Bogota
        (utc(2025, 3, 11, 1, 0, 0), True),  # 20:00:00 Bogota
        (utc(2025, 3, 10, 10, 59, 59), True),  # 05:59:59 Bogota
        (utc(2025, 3, 10, 11, 0, 0), False),  # 06:00:00 Bogota
        (utc(2025, 3, 11, 5, 0, 0), True),  # 00:00 Bogota
    ],
)
def test_R5_night_surcharge_boundaries(utc_time: datetime, night: bool) -> None:
    state = compute_delivery(happy_events(utc_time), BOGOTA)
    assert state.breakdown is not None
    assert (state.breakdown.night_surcharge_cents > 0) is night
    assert state.cost_cents == (18538 if night else 16120)


def test_R5_night_surcharge_is_15_percent_of_base_plus_distance() -> None:
    state = compute_delivery(happy_events(utc(2025, 3, 11, 3)), BOGOTA)  # 22:00 Bogota
    assert state.breakdown is not None
    assert state.breakdown.night_surcharge_cents == 2418  # 15% de 16120


def test_R11_same_instant_different_timezone_changes_result() -> None:
    instant = utc(2025, 3, 11, 3)  # 22:00 Bogota (noche) / 12:00 Tokyo (dia)
    tokyo = Tariff(base_fee_cents=5000, per_km_cents=100, timezone="Asia/Tokyo")
    assert compute_delivery(happy_events(instant), BOGOTA).cost_cents == 18538
    assert compute_delivery(happy_events(instant), tokyo).cost_cents == 16120


def test_R5_dst_uses_local_rules() -> None:
    # Nueva York 2025-03-09 salta a DST: 02:00 EST -> 03:00 EDT.
    # 2025-03-10 00:30 UTC = 20:30 EDT (UTC-4) del 9 de marzo => nocturno.
    ny = Tariff(base_fee_cents=5000, per_km_cents=100, timezone="America/New_York")
    state = compute_delivery(happy_events(utc(2025, 3, 10, 0, 30)), ny)
    assert state.cost_cents == 18538


# ---------- R6: fallida ----------
def test_R6_failed_charges_40_percent_of_base_without_surcharges() -> None:
    events = [
        ev("e1", EventType.CREADA, utc(2025, 3, 10, 12)),
        ev("e2", EventType.RECOGIDA, utc(2025, 3, 10, 12, 30), 0.0, 0.0),
        ev("e3", EventType.FALLIDA, utc(2025, 3, 11, 3)),  # nocturno, no debe recargar
    ]
    state = compute_delivery(events, BOGOTA)
    assert state.cost_cents == 2000
    assert state.cost_status == "calculado"
    assert state.breakdown is not None
    assert state.breakdown.distance_charge_cents == 0
    assert state.breakdown.night_surcharge_cents == 0


def test_R6_failed_needs_no_coordinates() -> None:
    events = [ev("e1", EventType.FALLIDA, utc(2025, 3, 10, 12))]
    assert compute_delivery(events, BOGOTA).cost_cents == 2000


# ---------- R7: idempotencia ----------
def test_R7_duplicate_events_do_not_change_cost() -> None:
    base = happy_events()
    once = compute_delivery(base, BOGOTA)
    many = compute_delivery(base + base + [base[4]], BOGOTA)
    assert many.cost_cents == once.cost_cents
    assert many.breakdown == once.breakdown
    assert many.anomalies == once.anomalies


def test_R7_same_id_different_content_is_conflict() -> None:
    a = ev("e5", EventType.ENTREGADA, DAY, 1.0, 0.0)
    b = ev("e5", EventType.ENTREGADA, DAY, 2.0, 0.0)
    with pytest.raises(ConflictingEventError):
        dedupe_events([a, b])
    with pytest.raises(ConflictingEventError):
        compute_delivery([a, b], BOGOTA)


# ---------- R8: desorden ----------
def test_R8_all_permutations_give_same_result() -> None:
    events = happy_events(utc(2025, 3, 11, 3))
    expected = compute_delivery(events, BOGOTA)
    for perm in itertools.permutations(events):
        assert compute_delivery(list(perm), BOGOTA) == expected


def test_R8_delivered_before_pickup_is_correct() -> None:
    events = [
        ev("e5", EventType.ENTREGADA, DAY, 1.0, 0.0),
        ev("e3", EventType.RECOGIDA, utc(2025, 3, 10, 12, 30), 0.0, 0.0),
    ]
    assert compute_delivery(events, BOGOTA).cost_cents == 16120


@given(st.permutations(happy_events(utc(2025, 3, 11, 3)) + happy_events(DAY)[:2]))
def test_R8_property_order_invariance(perm: list[Event]) -> None:
    # e1 y e2 repetidos (mismo contenido) -> duplicados legitimos
    assert compute_delivery(perm, BOGOTA) == compute_delivery(
        happy_events(utc(2025, 3, 11, 3)), BOGOTA
    )


# ---------- R9: pendiente ----------
def test_R9_delivered_without_pickup_is_pending() -> None:
    state = compute_delivery([ev("e5", EventType.ENTREGADA, DAY, 1.0, 0.0)], BOGOTA)
    assert state.cost_cents is None
    assert state.cost_status == "pendiente"


def test_R9_pending_completes_when_missing_event_arrives() -> None:
    first = [ev("e5", EventType.ENTREGADA, DAY, 1.0, 0.0)]
    assert compute_delivery(first, BOGOTA).cost_status == "pendiente"
    second = first + [ev("e3", EventType.RECOGIDA, utc(2025, 3, 10, 12, 30), 0.0, 0.0)]
    assert compute_delivery(second, BOGOTA).cost_cents == 16120


# ---------- R10: fallida tardia ----------
def test_R10_late_failed_after_delivered_is_anomaly_only() -> None:
    events = happy_events() + [ev("e6", EventType.FALLIDA, utc(2025, 3, 10, 16))]
    state = compute_delivery(events, BOGOTA)
    assert state.status == EventType.ENTREGADA
    assert state.cost_cents == 16120
    assert any("fallida" in a for a in state.anomalies)


# ---------- R12: trazabilidad ----------
def test_R12_breakdown_is_auditable() -> None:
    state = compute_delivery(happy_events(utc(2025, 3, 11, 3)), BOGOTA)
    b = state.breakdown
    assert b is not None
    assert b.base_fee_cents == 5000
    assert b.per_km_cents == 100
    assert b.night_surcharge_percent == 15
    assert b.timezone == "America/Bogota"
    assert b.local_delivery_time is not None
    assert set(b.event_ids_used) == {"e3", "e5"}
    assert b.algorithm_version


# ---------- S7 / S8 ----------
def test_S7_mixed_merchants_is_inconsistent() -> None:
    events = [
        ev("e1", EventType.CREADA, utc(2025, 3, 10, 12), merchant="m1"),
        ev("e2", EventType.ASIGNADA, utc(2025, 3, 10, 12, 5), merchant="m2"),
    ]
    with pytest.raises(InconsistentEventsError):
        compute_delivery(events, BOGOTA)


def test_S8_two_pickups_picks_earliest_and_records_anomaly() -> None:
    events = happy_events() + [
        ev("e3b", EventType.RECOGIDA, utc(2025, 3, 10, 13), 50.0, 50.0),
    ]
    state = compute_delivery(events, BOGOTA)
    assert state.cost_cents == 16120  # usa la recogida e3 (la mas temprana)
    assert any("recogida" in a for a in state.anomalies)


def test_event_requires_coordinates_for_pickup_and_delivery() -> None:
    with pytest.raises(ValueError):
        ev("x", EventType.RECOGIDA, DAY)
    with pytest.raises(ValueError):
        ev("x", EventType.ENTREGADA, DAY, 1.0, None)


def test_event_requires_timezone_aware_datetime() -> None:
    with pytest.raises(ValueError):
        ev("x", EventType.CREADA, datetime(2025, 3, 10, 12))
