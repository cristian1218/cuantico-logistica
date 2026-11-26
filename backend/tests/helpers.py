"""Helpers compartidos por los tests de API."""

from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient

ADMIN = {"Authorization": "Bearer tok-admin-01"}
LA80 = {"Authorization": "Bearer tok-la80-001"}
CAFE = {"Authorization": "Bearer tok-cafe-001"}


def event_json(
    eid: str,
    etype: str,
    at: str,
    lat: float | None = None,
    lon: float | None = None,
    delivery: str = "d1",
    merchant: str = "m-la80",
    courier: str = "c-ana",
    address: str | None = None,
) -> dict[str, Any]:
    body: dict[str, Any] = {
        "event_id": eid,
        "delivery_id": delivery,
        "merchant_id": merchant,
        "courier_id": courier,
        "type": etype,
        "occurred_at": at,
    }
    if lat is not None:
        body["lat"] = lat
    if lon is not None:
        body["lon"] = lon
    if address is not None:
        body["address"] = address
    return body


def delivered_flow(
    delivery: str,
    delivered_at: str,
    merchant: str = "m-la80",
    courier: str = "c-ana",
    address: str | None = None,
) -> list[dict[str, Any]]:
    """creada -> recogida (0,0) -> entregada (1,0): 111.195 km."""
    created = event_json(
        f"{delivery}-1",
        "creada",
        "2026-11-17T12:00:00Z",
        delivery=delivery,
        merchant=merchant,
        courier=courier,
        address=address,
    )
    picked = event_json(
        f"{delivery}-3",
        "recogida",
        "2026-11-17T12:30:00Z",
        0.0,
        0.0,
        delivery=delivery,
        merchant=merchant,
        courier=courier,
    )
    delivered = event_json(
        f"{delivery}-5",
        "entregada",
        delivered_at,
        1.0,
        0.0,
        delivery=delivery,
        merchant=merchant,
        courier=courier,
    )
    return [created, picked, delivered]


def post_all(
    client: TestClient, events: list[dict[str, Any]], headers: dict[str, str] = ADMIN
) -> None:
    for e in events:
        r = client.post("/api/events", json=e, headers=headers)
        assert r.status_code in (200, 201), r.text
