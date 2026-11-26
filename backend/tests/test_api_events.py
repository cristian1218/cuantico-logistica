"""Ingesta de eventos por HTTP: idempotencia, desorden, validacion y alcance."""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.store import repository as repo
from tests.helpers import ADMIN, CAFE, LA80, delivered_flow, event_json, post_all


def get_delivery(client: TestClient, delivery_id: str) -> dict[str, Any]:
    r = client.get(f"/api/deliveries/{delivery_id}", headers=ADMIN)
    assert r.status_code == 200, r.text
    body: dict[str, Any] = r.json()
    return body


def test_health_is_public(client: TestClient) -> None:
    assert client.get("/api/health").json() == {"status": "ok"}


# ---------- autenticacion (SEC3) ----------
def test_SEC3_events_require_token(client: TestClient) -> None:
    r = client.post("/api/events", json=event_json("e1", "creada", "2026-11-17T12:00:00Z"))
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "unauthorized"


def test_SEC3_wrong_token_is_rejected(client: TestClient) -> None:
    r = client.get("/api/deliveries/d1", headers={"Authorization": "Bearer nope-nope-nope"})
    assert r.status_code == 401


def test_SEC3_ingest_outside_scope_is_403(client: TestClient) -> None:
    event = event_json("e1", "creada", "2026-11-17T12:00:00Z", merchant="m-cafe")
    assert client.post("/api/events", json=event, headers=LA80).status_code == 403
    assert client.post("/api/events", json=event, headers=CAFE).status_code == 201


# ---------- R7 idempotencia ----------
def test_R7_duplicate_returns_200_and_does_not_change_cost(client: TestClient) -> None:
    flow = delivered_flow("d1", "2026-11-17T15:00:00Z")
    for e in flow:
        assert client.post("/api/events", json=e, headers=ADMIN).status_code == 201
    before = get_delivery(client, "d1")
    assert before["cost_cents"] == 16120

    for _ in range(3):
        r = client.post("/api/events", json=flow[2], headers=ADMIN)
        assert r.status_code == 200
        assert r.json()["duplicate"] is True
    assert get_delivery(client, "d1") == before


def test_R7_same_id_different_content_is_409_and_changes_nothing(client: TestClient) -> None:
    post_all(client, delivered_flow("d1", "2026-11-17T15:00:00Z"))
    before = get_delivery(client, "d1")
    tampered = event_json(
        "d1-5", "entregada", "2026-11-17T15:00:00Z", 5.0, 0.0, delivery="d1"
    )  # mismo event_id, otras coordenadas
    r = client.post("/api/events", json=tampered, headers=ADMIN)
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "conflicting_event"
    assert get_delivery(client, "d1") == before


# ---------- R8 / R9 desorden ----------
def test_R8_R9_out_of_order_via_api(client: TestClient) -> None:
    creada, recogida, entregada = delivered_flow("d1", "2026-11-17T15:00:00Z")
    r = client.post("/api/events", json=entregada, headers=ADMIN)
    assert r.status_code == 201
    first = r.json()["delivery"]
    assert first["status"] == "entregada"
    assert first["cost_status"] == "pendiente"
    assert first["cost_cents"] is None

    client.post("/api/events", json=recogida, headers=ADMIN)
    client.post("/api/events", json=creada, headers=ADMIN)
    final = get_delivery(client, "d1")
    assert final["cost_status"] == "calculado"
    assert final["cost_cents"] == 16120


def test_R5_night_surcharge_via_api(client: TestClient) -> None:
    post_all(client, delivered_flow("d2", "2026-11-18T02:30:00Z"))  # 21:30 Bogota
    assert get_delivery(client, "d2")["cost_cents"] == 18538


def test_R6_failed_via_api(client: TestClient) -> None:
    post_all(
        client,
        [
            event_json("f-1", "creada", "2026-11-17T12:00:00Z", delivery="d3"),
            event_json("f-2", "fallida", "2026-11-17T13:00:00Z", delivery="d3"),
        ],
    )
    d = get_delivery(client, "d3")
    assert d["status"] == "fallida"
    assert d["cost_cents"] == 2000


def test_R12_breakdown_is_exposed(client: TestClient) -> None:
    post_all(client, delivered_flow("d1", "2026-11-18T02:30:00Z"))
    b = get_delivery(client, "d1")["breakdown"]
    assert b["base_fee_cents"] == 5000
    assert b["night_surcharge_cents"] == 2418
    assert b["timezone"] == "America/Bogota"
    assert sorted(b["event_ids_used"]) == ["d1-3", "d1-5"]


def test_S7_mixed_merchant_is_409_and_event_not_stored(client: TestClient) -> None:
    post_all(client, [event_json("e1", "creada", "2026-11-17T12:00:00Z")])
    other = event_json("e2", "asignada", "2026-11-17T12:05:00Z", merchant="m-cafe")
    r = client.post("/api/events", json=other, headers=ADMIN)
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "inconsistent_events"
    # reintento valido del evento correcto sigue funcionando (nada quedo a medias)
    ok = event_json("e2", "asignada", "2026-11-17T12:05:00Z")
    assert client.post("/api/events", json=ok, headers=ADMIN).status_code == 201


def test_S9_address_is_taken_from_earliest_event_that_has_one(client: TestClient) -> None:
    post_all(
        client,
        [
            event_json("e2", "asignada", "2026-11-17T12:05:00Z", address="Otra 2"),
            event_json("e1", "creada", "2026-11-17T12:00:00Z", address="Calle 1"),
        ],
    )
    assert get_delivery(client, "d1")["address"] == "Calle 1"


# ---------- validacion ----------
@pytest.mark.parametrize(
    "mutation",
    [
        {"event_id": None},  # falta (se elimina)
        {"event_id": ""},
        {"type": "teletransportada"},
        {"occurred_at": "2026-11-17T12:00:00"},  # sin zona horaria
        {"occurred_at": "no-es-fecha"},
        {"lat": 123.0, "lon": 0.0},
        {"surprise": "campo extra"},
        {"delivery_id": "x" * 65},
    ],
)
def test_invalid_payload_is_422(client: TestClient, mutation: dict[str, Any]) -> None:
    body = event_json("e1", "creada", "2026-11-17T12:00:00Z")
    for key, value in mutation.items():
        if value is None:
            body.pop(key)
        else:
            body[key] = value
    r = client.post("/api/events", json=body, headers=ADMIN)
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "validation_error"


def test_pickup_without_coordinates_is_422(client: TestClient) -> None:
    r = client.post(
        "/api/events", json=event_json("e1", "recogida", "2026-11-17T12:00:00Z"), headers=ADMIN
    )
    assert r.status_code == 422


def test_unknown_merchant_is_422(client: TestClient) -> None:
    event = event_json("e1", "creada", "2026-11-17T12:00:00Z", merchant="m-fantasma")
    r = client.post("/api/events", json=event, headers=ADMIN)
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "unknown_merchant"


# ---------- errores sin fugas ----------
def test_unknown_route_uses_error_envelope(client: TestClient) -> None:
    r = client.get("/api/nope", headers=ADMIN)
    assert r.status_code == 404
    assert "error" in r.json()


def test_internal_errors_do_not_leak_details(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    def boom(*_: Any, **__: Any) -> None:
        raise RuntimeError("secreto-interno-xyz")

    monkeypatch.setattr(repo, "ingest_event", boom)
    r = client.post(
        "/api/events", json=event_json("e1", "creada", "2026-11-17T12:00:00Z"), headers=ADMIN
    )
    assert r.status_code == 500
    assert "secreto-interno-xyz" not in r.text
    assert r.json()["error"]["code"] == "internal_error"
