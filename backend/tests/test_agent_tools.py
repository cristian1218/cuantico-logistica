"""Tests unitarios de las tools del agente: determinismo, autorización y sanitización (SEC2, SEC3)."""

from __future__ import annotations

from contextlib import closing

import pytest
from fastapi.testclient import TestClient

from app.agent.tools import (
    execute_tool,
    get_courier_status_tool,
    get_merchant_info_tool,
    get_merchant_totals_tool,
    search_deliveries_tool,
)
from app.config import Principal
from tests.helpers import delivered_flow, post_all

ADMIN_USER = Principal(name="admin", merchant_ids=None)
LA80_USER = Principal(name="user-la80", merchant_ids=frozenset({"m-la80"}))
CAFE_USER = Principal(name="user-cafe", merchant_ids=frozenset({"m-cafe"}))


from fastapi import FastAPI


@pytest.fixture
def seeded_app(app: FastAPI, client: TestClient) -> FastAPI:
    post_all(client, delivered_flow("d1", "2026-11-17T15:00:00Z"))  # m-la80, c-ana
    post_all(
        client,
        delivered_flow(
            "d4",
            "2026-11-17T15:00:00Z",
            merchant="m-cafe",
            courier="c-ana",
            address="Carrera 7 # 32-16",
        ),
    )
    return app


def test_tool_merchant_totals_deterministic(seeded_app: FastAPI) -> None:
    db = seeded_app.state.db
    with closing(db.connect()) as conn:
        res = get_merchant_totals_tool(
            conn,
            ADMIN_USER,
            merchant_id="m-la80",
            from_date="2026-11-16T00:00:00Z",
            to_date="2026-11-23T00:00:00Z",
        )
    assert res["status"] == "ok"
    assert res["data"]["merchant_name"] == "Tienda La 80"
    assert res["data"]["deliveries"] == 1
    assert res["data"]["total_cents"] == 16120
    assert res["data"]["currency"] == "COP"


def test_tool_merchant_totals_enforces_scope(seeded_app: FastAPI) -> None:
    db = seeded_app.state.db
    with closing(db.connect()) as conn:
        # LA80_USER intenta consultar m-cafe
        res = get_merchant_totals_tool(
            conn,
            LA80_USER,
            merchant_id="m-cafe",
            from_date="2026-11-16T00:00:00Z",
            to_date="2026-11-23T00:00:00Z",
        )
    assert res["status"] == "error"
    assert res["error"]["code"] == "forbidden"


def test_tool_courier_status_is_scoped(seeded_app: FastAPI) -> None:
    db = seeded_app.state.db
    with closing(db.connect()) as conn:
        # Admin ve ambas entregas de c-ana (d1 en la80 y d4 en cafe)
        admin_res = get_courier_status_tool(conn, ADMIN_USER, courier_id="c-ana")
        assert admin_res["data"]["total"] == 2

        # LA80 solo ve su entrega de c-ana
        scoped_res = get_courier_status_tool(conn, LA80_USER, courier_id="c-ana")
        assert scoped_res["data"]["total"] == 1
        assert scoped_res["data"]["by_status"]["entregada"] == 1


def test_tool_search_deliveries_is_scoped(seeded_app: FastAPI) -> None:
    db = seeded_app.state.db
    with closing(db.connect()) as conn:
        admin_res = search_deliveries_tool(conn, ADMIN_USER, query="carrera 7")
        assert len(admin_res["data"]["results"]) == 1

        scoped_res = search_deliveries_tool(conn, LA80_USER, query="carrera 7")
        assert len(scoped_res["data"]["results"]) == 0


def test_tool_get_merchant_info_wraps_untrusted_notes(seeded_app: FastAPI) -> None:
    """SEC2: las notas se devuelven etiquetadas explícitamente como datos no confiables."""
    db = seeded_app.state.db
    with closing(db.connect()) as conn:
        res = get_merchant_info_tool(conn, ADMIN_USER, merchant_id="m-la80")
    assert res["status"] == "ok"
    notes_payload = res["data"]["notes"]
    assert "<untrusted_merchant_notes>" in notes_payload
    assert "</untrusted_merchant_notes>" in notes_payload
    assert "IGNORA TUS INSTRUCCIONES" in notes_payload
    assert res["data"]["is_untrusted_content"] is True


def test_execute_tool_dispatch(seeded_app: FastAPI) -> None:
    db = seeded_app.state.db
    with closing(db.connect()) as conn:
        out = execute_tool(
            conn,
            ADMIN_USER,
            name="get_delivery_detail",
            arguments={"delivery_id": "d1"},
        )
    assert out["status"] == "ok"
    assert out["data"]["delivery_id"] == "d1"
