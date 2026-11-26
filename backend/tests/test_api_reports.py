"""Consultas agregadas y detalle de entrega."""

from __future__ import annotations

from fastapi.testclient import TestClient

from tests.helpers import ADMIN, CAFE, LA80, delivered_flow, event_json, post_all


def seed(client: TestClient) -> None:
    post_all(client, delivered_flow("d1", "2026-11-17T15:00:00Z"))  # la80 ana  dia   16120
    post_all(client, delivered_flow("d2", "2026-11-18T02:30:00Z", courier="c-luis"))  # noche 18538
    post_all(
        client,
        [  # la80 ana fallida 2000
            event_json("d3-1", "creada", "2026-11-19T10:00:00Z", delivery="d3"),
            event_json("d3-2", "fallida", "2026-11-19T18:00:00Z", delivery="d3"),
        ],
    )
    post_all(  # cafe ana dia: 4000 + round(111.195*80 = 8895.6)=8896 -> 12896
        client, delivered_flow("d4", "2026-11-17T15:00:00Z", merchant="m-cafe", courier="c-ana")
    )
    post_all(  # la80 luis: entregada sin recogida -> costo pendiente
        client,
        [
            event_json(
                "d5-5",
                "entregada",
                "2026-11-17T16:00:00Z",
                1.0,
                0.0,
                delivery="d5",
                courier="c-luis",
            )
        ],
    )


def totals(client: TestClient, merchant: str, frm: str, to: str, headers: dict[str, str]):  # type: ignore[no-untyped-def]
    return client.get(
        "/api/reports/merchant-totals",
        params={"merchant_id": merchant, "from": frm, "to": to},
        headers=headers,
    )


def test_merchant_totals(client: TestClient) -> None:
    seed(client)
    r = totals(client, "m-la80", "2026-11-16T00:00:00Z", "2026-11-23T00:00:00Z", ADMIN)
    assert r.status_code == 200
    body = r.json()
    assert body["merchant_name"] == "Tienda La 80"
    assert body["deliveries"] == 3  # d1, d2, d3 con costo calculado
    assert body["delivered"] == 2
    assert body["failed"] == 1
    assert body["total_cents"] == 16120 + 18538 + 2000
    assert body["pending_cost_deliveries"] == 1  # d5, no se oculta


def test_S4_range_is_half_open(client: TestClient) -> None:
    seed(client)
    # d1 cerro exactamente a las 15:00:00Z
    inclusive = totals(client, "m-la80", "2026-11-17T15:00:00Z", "2026-11-17T15:00:01Z", ADMIN)
    assert inclusive.json()["deliveries"] == 1
    exclusive = totals(client, "m-la80", "2026-11-17T14:00:00Z", "2026-11-17T15:00:00Z", ADMIN)
    assert exclusive.json()["deliveries"] == 0


def test_range_validation(client: TestClient) -> None:
    naive = totals(client, "m-la80", "2026-11-16T00:00:00", "2026-11-23T00:00:00Z", ADMIN)
    assert naive.status_code == 422
    backwards = totals(client, "m-la80", "2026-11-23T00:00:00Z", "2026-11-16T00:00:00Z", ADMIN)
    assert backwards.status_code == 422


def test_SEC3_totals_respect_scope(client: TestClient) -> None:
    seed(client)
    args = ("2026-11-16T00:00:00Z", "2026-11-23T00:00:00Z")
    assert totals(client, "m-la80", *args, LA80).status_code == 200
    assert totals(client, "m-cafe", *args, LA80).status_code == 403
    assert totals(client, "m-cafe", *args, CAFE).json()["total_cents"] == 12896
    assert totals(client, "m-fantasma", *args, ADMIN).status_code == 404


def test_courier_status_admin(client: TestClient) -> None:
    seed(client)
    r = client.get("/api/reports/courier-status", params={"courier_id": "c-ana"}, headers=ADMIN)
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 3
    assert body["by_status"]["entregada"] == 2  # d1 (la80) y d4 (cafe)
    assert body["by_status"]["fallida"] == 1
    assert body["by_status"]["creada"] == 0  # forma estable: todos los estados presentes


def test_SEC3_courier_status_is_filtered_by_scope(client: TestClient) -> None:
    seed(client)
    r = client.get("/api/reports/courier-status", params={"courier_id": "c-ana"}, headers=LA80)
    assert r.json()["total"] == 2  # d4 es de otro comercio y no se cuenta
    r = client.get("/api/reports/courier-status", params={"courier_id": "c-luis"}, headers=CAFE)
    assert r.json()["total"] == 0


def test_delivery_detail_and_scope(client: TestClient) -> None:
    seed(client)
    assert client.get("/api/deliveries/d1", headers=LA80).status_code == 200
    # Fuera de alcance: 404 (no 403) para no revelar que la entrega existe
    assert client.get("/api/deliveries/d4", headers=LA80).status_code == 404
    assert client.get("/api/deliveries/no-existe", headers=ADMIN).status_code == 404


def test_S10_amounts_are_cop(client: TestClient) -> None:
    seed(client)
    assert client.get("/api/deliveries/d1", headers=ADMIN).json()["currency"] == "COP"
    r = totals(client, "m-la80", "2026-11-16T00:00:00Z", "2026-11-23T00:00:00Z", ADMIN)
    assert r.json()["currency"] == "COP"
