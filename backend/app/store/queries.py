"""Consultas agregadas y buscador. SEC1: todo valor de usuario va enlazado como parametro.

`scope` es el alcance del usuario autenticado: None = global; un conjunto = solo esos comercios.
El unico texto que se interpola en SQL son marcadores `?` generados por nosotros (nunca datos).
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime

from app.store.repository import iso_utc

SEARCH_LIMIT = 50


def escape_like(text: str) -> str:
    r"""Neutraliza los comodines de LIKE: `\`, `%` y `_` se buscan literalmente."""
    return text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _scope_clause(column: str, scope: frozenset[str] | None) -> tuple[str, list[str]]:
    if scope is None:
        return "", []
    if not scope:
        return " AND 0", []
    placeholders = ",".join("?" for _ in scope)
    return f" AND {column} IN ({placeholders})", sorted(scope)


@dataclass(frozen=True)
class MerchantTotals:
    deliveries: int
    delivered: int
    failed: int
    total_cents: int
    pending_cost_deliveries: int


def merchant_totals(
    conn: sqlite3.Connection, merchant_id: str, start: datetime, end: datetime
) -> MerchantTotals:
    """S4: entregas cerradas en [start, end). Las de costo pendiente se cuentan aparte."""
    row = conn.execute(
        "SELECT "
        " COALESCE(SUM(cost_status = 'calculado'), 0) AS deliveries, "
        " COALESCE(SUM(cost_status = 'calculado' AND status = 'entregada'), 0) AS delivered, "
        " COALESCE(SUM(cost_status = 'calculado' AND status = 'fallida'), 0) AS failed, "
        " COALESCE(SUM(CASE WHEN cost_status = 'calculado' THEN cost_cents END), 0) AS total, "
        " COALESCE(SUM(cost_status = 'pendiente'), 0) AS pending "
        "FROM deliveries WHERE merchant_id = ? AND closed_at >= ? AND closed_at < ?",
        (merchant_id, iso_utc(start), iso_utc(end)),
    ).fetchone()
    return MerchantTotals(
        deliveries=row["deliveries"],
        delivered=row["delivered"],
        failed=row["failed"],
        total_cents=row["total"],
        pending_cost_deliveries=row["pending"],
    )


def courier_status_counts(
    conn: sqlite3.Connection, courier_id: str, scope: frozenset[str] | None
) -> dict[str, int]:
    clause, params = _scope_clause("merchant_id", scope)
    rows = conn.execute(
        "SELECT status, COUNT(*) AS n FROM deliveries WHERE courier_id = ?"
        + clause
        + " GROUP BY status",
        (courier_id, *params),
    ).fetchall()
    return {r["status"]: r["n"] for r in rows}


@dataclass(frozen=True)
class SearchHit:
    delivery_id: str
    merchant_id: str
    merchant_name: str
    courier_id: str
    courier_name: str | None
    address: str | None
    status: str
    cost_status: str
    cost_cents: int | None


def search_deliveries(
    conn: sqlite3.Connection, text: str, scope: frozenset[str] | None
) -> list[SearchHit]:
    """Busca `text` como subcadena literal en comercio, direccion o mensajero.

    No devuelve notas del comercio: son datos no confiables que no deben circular (SEC2).
    """
    pattern = f"%{escape_like(text)}%"
    clause, params = _scope_clause("d.merchant_id", scope)
    rows = conn.execute(
        "SELECT d.delivery_id, d.merchant_id, m.name AS merchant_name, d.courier_id, "
        " c.name AS courier_name, d.address, d.status, d.cost_status, d.cost_cents "
        "FROM deliveries d "
        "JOIN merchants m ON m.id = d.merchant_id "
        "LEFT JOIN couriers c ON c.id = d.courier_id "
        "WHERE (m.name LIKE ? ESCAPE '\\' OR d.address LIKE ? ESCAPE '\\' "
        " OR c.name LIKE ? ESCAPE '\\')" + clause + " ORDER BY d.delivery_id LIMIT ?",
        (pattern, pattern, pattern, *params, SEARCH_LIMIT),
    ).fetchall()
    return [SearchHit(**dict(r)) for r in rows]
