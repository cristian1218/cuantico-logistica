"""Repositorio: ingesta transaccional de eventos y lectura de entregas.

Toda consulta usa parametros enlazados (`?`). Ningun valor de usuario se concatena en SQL.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import Any

from app.domain.costing import compute_delivery
from app.domain.errors import ConflictingEventError
from app.domain.models import DeliveryState, Event, EventType, Tariff


class UnknownMerchantError(Exception):
    pass


@dataclass(frozen=True)
class MerchantRow:
    id: str
    name: str
    timezone: str
    base_fee_cents: int
    per_km_cents: int
    notes: str

    @property
    def tariff(self) -> Tariff:
        return Tariff(self.base_fee_cents, self.per_km_cents, self.timezone)


@dataclass(frozen=True)
class DeliveryRecord:
    delivery_id: str
    merchant_id: str
    courier_id: str
    status: str
    cost_status: str
    cost_cents: int | None
    closed_at: str | None
    address: str | None
    breakdown: dict[str, Any] | None
    anomalies: list[str]


@dataclass(frozen=True)
class IngestResult:
    duplicate: bool
    delivery_id: str


def iso_utc(moment: datetime) -> str:
    """Formato unico y de ancho fijo => la comparacion lexicografica equivale a la temporal."""
    return moment.astimezone(UTC).isoformat(timespec="microseconds")


# ---------- comercios y mensajeros ----------
def upsert_merchant(conn: sqlite3.Connection, m: MerchantRow) -> None:
    conn.execute(
        "INSERT INTO merchants (id, name, timezone, base_fee_cents, per_km_cents, notes) "
        "VALUES (?, ?, ?, ?, ?, ?) "
        "ON CONFLICT(id) DO UPDATE SET name=excluded.name, timezone=excluded.timezone, "
        "base_fee_cents=excluded.base_fee_cents, per_km_cents=excluded.per_km_cents, "
        "notes=excluded.notes",
        (m.id, m.name, m.timezone, m.base_fee_cents, m.per_km_cents, m.notes),
    )


def upsert_courier(conn: sqlite3.Connection, courier_id: str, name: str) -> None:
    conn.execute(
        "INSERT INTO couriers (id, name) VALUES (?, ?) "
        "ON CONFLICT(id) DO UPDATE SET name=excluded.name",
        (courier_id, name),
    )


def get_merchant(conn: sqlite3.Connection, merchant_id: str) -> MerchantRow | None:
    row = conn.execute(
        "SELECT id, name, timezone, base_fee_cents, per_km_cents, notes FROM merchants WHERE id = ?",
        (merchant_id,),
    ).fetchone()
    return None if row is None else MerchantRow(**dict(row))


# ---------- eventos ----------
def _event_from_row(row: sqlite3.Row) -> Event:
    return Event(
        event_id=row["event_id"],
        delivery_id=row["delivery_id"],
        merchant_id=row["merchant_id"],
        courier_id=row["courier_id"],
        type=EventType(row["type"]),
        occurred_at=datetime.fromisoformat(row["occurred_at"]),
        lat=row["lat"],
        lon=row["lon"],
        address=row["address"],
    )


def _load_events(conn: sqlite3.Connection, delivery_id: str) -> list[Event]:
    rows = conn.execute("SELECT * FROM events WHERE delivery_id = ?", (delivery_id,)).fetchall()
    return [_event_from_row(r) for r in rows]


def _earliest_address(events: list[Event]) -> str | None:
    """S9: direccion del evento mas temprano que traiga una."""
    with_address = sorted(
        (e for e in events if e.address), key=lambda e: (e.occurred_at, e.event_id)
    )
    return with_address[0].address if with_address else None


def _save_delivery(
    conn: sqlite3.Connection, state: DeliveryState, address: str | None, now: datetime
) -> None:
    breakdown = json.dumps(asdict(state.breakdown)) if state.breakdown else None
    conn.execute(
        "INSERT INTO deliveries (delivery_id, merchant_id, courier_id, status, cost_status, "
        "cost_cents, closed_at, address, breakdown_json, anomalies_json, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) "
        "ON CONFLICT(delivery_id) DO UPDATE SET status=excluded.status, "
        "cost_status=excluded.cost_status, cost_cents=excluded.cost_cents, "
        "closed_at=excluded.closed_at, address=excluded.address, "
        "breakdown_json=excluded.breakdown_json, anomalies_json=excluded.anomalies_json, "
        "updated_at=excluded.updated_at",
        (
            state.delivery_id,
            state.merchant_id,
            state.courier_id,
            state.status.value,
            state.cost_status,
            state.cost_cents,
            iso_utc(state.closed_at) if state.closed_at else None,
            address,
            breakdown,
            json.dumps(list(state.anomalies)),
            iso_utc(now),
        ),
    )


def ingest_event(conn: sqlite3.Connection, event: Event) -> IngestResult:
    """Guarda el evento (R7) y recalcula la entrega desde todos sus eventos (R8), atomicamente.

    BEGIN IMMEDIATE toma el bloqueo de escritura desde el inicio: dos eventos concurrentes de
    la misma entrega se serializan y el segundo recalcula viendo el primero.
    """
    conn.execute("BEGIN IMMEDIATE")
    try:
        merchant = get_merchant(conn, event.merchant_id)
        if merchant is None:
            raise UnknownMerchantError(event.merchant_id)

        existing = conn.execute(
            "SELECT * FROM events WHERE event_id = ?", (event.event_id,)
        ).fetchone()
        if existing is not None:
            if _event_from_row(existing) != event:
                raise ConflictingEventError(
                    f"event_id '{event.event_id}' reutilizado con contenido distinto"
                )
            conn.execute("COMMIT")
            return IngestResult(duplicate=True, delivery_id=event.delivery_id)

        # Si los eventos son inconsistentes (S7) esto lanza ANTES de escribir nada.
        events = [*_load_events(conn, event.delivery_id), event]
        state = compute_delivery(events, merchant.tariff)

        now = datetime.now(UTC)
        conn.execute(
            "INSERT INTO events (event_id, delivery_id, merchant_id, courier_id, type, "
            "occurred_at, lat, lon, address, received_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                event.event_id,
                event.delivery_id,
                event.merchant_id,
                event.courier_id,
                event.type.value,
                iso_utc(event.occurred_at),
                event.lat,
                event.lon,
                event.address,
                iso_utc(now),
            ),
        )
        _save_delivery(conn, state, _earliest_address(events), now)
        conn.execute("COMMIT")
        return IngestResult(duplicate=False, delivery_id=event.delivery_id)
    except BaseException:
        conn.execute("ROLLBACK")
        raise


# ---------- lectura ----------
def get_delivery(conn: sqlite3.Connection, delivery_id: str) -> DeliveryRecord | None:
    row = conn.execute("SELECT * FROM deliveries WHERE delivery_id = ?", (delivery_id,)).fetchone()
    if row is None:
        return None
    return DeliveryRecord(
        delivery_id=row["delivery_id"],
        merchant_id=row["merchant_id"],
        courier_id=row["courier_id"],
        status=row["status"],
        cost_status=row["cost_status"],
        cost_cents=row["cost_cents"],
        closed_at=row["closed_at"],
        address=row["address"],
        breakdown=json.loads(row["breakdown_json"]) if row["breakdown_json"] else None,
        anomalies=json.loads(row["anomalies_json"]),
    )
