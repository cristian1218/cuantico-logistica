"""SEC1: el buscador de texto libre no es vulnerable a inyeccion SQL."""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient

from tests.helpers import ADMIN, CAFE, LA80, delivered_flow, event_json, post_all


def search(client: TestClient, q: str, headers: dict[str, str] = ADMIN) -> Any:
    return client.get("/api/deliveries/search", params={"q": q}, headers=headers)


@pytest.fixture
def data(client: TestClient) -> TestClient:
    post_all(
        client, delivered_flow("d1", "2026-11-17T15:00:00Z", address="Calle 80 # 69-20, Bogota")
    )
    post_all(
        client,
        delivered_flow(
            "d4",
            "2026-11-17T15:00:00Z",
            merchant="m-cafe",
            courier="c-luis",
            address="Carrera 7 # 32-16",
        ),
    )
    post_all(
        client,
        [
            event_json(
                "d9-1",
                "creada",
                "2026-11-17T12:00:00Z",
                delivery="d9",
                address="Promo 50% off Calle 1_B",
            )
        ],
    )
    return client


def ids(response: Any) -> set[str]:
    assert response.status_code == 200, response.text
    return {r["delivery_id"] for r in response.json()["results"]}


def test_search_by_merchant_name_is_case_insensitive(data: TestClient) -> None:
    assert ids(search(data, "tienda la 80")) == {"d1", "d9"}


def test_search_by_address(data: TestClient) -> None:
    assert ids(search(data, "carrera 7")) == {"d4"}


def test_search_by_courier_name(data: TestClient) -> None:
    assert ids(search(data, "Luis")) == {"d4"}


@pytest.mark.parametrize(
    "payload",
    [
        "' OR 1=1 --",
        "' OR '1'='1",
        "%' OR 1=1 --",
        "'; DROP TABLE deliveries; --",
        "\\",
        "'; DELETE FROM events; --",
        '" OR ""="',
    ],
)
def test_SEC1_injection_payloads_match_nothing_and_break_nothing(
    data: TestClient, payload: str
) -> None:
    assert ids(search(data, payload)) == set()
    # las tablas siguen intactas
    assert data.get("/api/deliveries/d1", headers=ADMIN).status_code == 200


def test_SEC1_percent_and_underscore_are_literals(data: TestClient) -> None:
    # '%' solo encuentra el registro que contiene un '%' literal, no todos
    assert ids(search(data, "%")) == {"d9"}
    assert ids(search(data, "50%")) == {"d9"}
    # '_' solo encuentra el que contiene '_' literal ("1_B"), no cualquier caracter
    assert ids(search(data, "_")) == {"d9"}
    assert ids(search(data, "1_B")) == {"d9"}
    assert ids(search(data, "1xB")) == set()


def test_SEC1_results_are_capped_at_50(client: TestClient) -> None:
    for i in range(60):
        post_all(
            client,
            [event_json(f"x{i}-1", "creada", "2026-11-17T12:00:00Z", delivery=f"x{i}")],
        )
    r = search(client, "Tienda")
    assert r.status_code == 200
    assert r.json()["count"] == 50


def test_SEC3_search_is_limited_to_scope(data: TestClient) -> None:
    assert ids(search(data, "Luis", LA80)) == set()  # c-luis solo aparece en cafe (d4)
    assert ids(search(data, "Luis", CAFE)) == {"d4"}
    assert ids(search(data, "tienda", CAFE)) == set()


def test_SEC2_search_never_returns_merchant_notes(data: TestClient) -> None:
    r = search(data, "tienda la 80")
    assert "IGNORA" not in r.text
    assert "notes" not in r.text


@pytest.mark.parametrize("q", ["", "x" * 101])
def test_search_query_length_is_validated(data: TestClient, q: str) -> None:
    assert search(data, q).status_code == 422


def test_search_requires_q(data: TestClient) -> None:
    assert data.get("/api/deliveries/search", headers=ADMIN).status_code == 422
