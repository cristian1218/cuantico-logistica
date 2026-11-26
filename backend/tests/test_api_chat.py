"""Tests del endpoint HTTP /api/chat."""

from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient

from tests.helpers import ADMIN, LA80, delivered_flow, post_all


def test_chat_requires_auth(client: TestClient) -> None:
    res = client.post("/api/chat", json={"message": "¿Cuánto facturó Tienda La 80?"})
    assert res.status_code == 401
    assert res.json()["error"]["code"] == "unauthorized"


def test_chat_happy_path_with_mock_llm(client: TestClient) -> None:
    post_all(client, delivered_flow("d1", "2026-11-17T15:00:00Z"))
    res = client.post(
        "/api/chat",
        json={
            "message": "¿Cuánto facturó Tienda La 80 la semana del 16 al 23 de noviembre de 2026?"
        },
        headers=ADMIN,
    )
    assert res.status_code == 200
    body: dict[str, Any] = res.json()
    assert "answer" in body
    assert "tool_calls" in body
    assert len(body["tool_calls"]) > 0
    first_call = body["tool_calls"][0]
    assert first_call["name"] == "get_merchant_totals"
    assert first_call["args"]["merchant_id"] == "m-la80"
    assert first_call["result"]["status"] == "ok"
    assert first_call["result"]["data"]["total_cents"] == 16120


def test_chat_scoped_user_cannot_query_foreign_merchant(client: TestClient) -> None:
    post_all(client, delivered_flow("d1", "2026-11-17T15:00:00Z"))
    # LA80 intenta consultar sobre Café Central
    res = client.post(
        "/api/chat",
        json={"message": "¿Cuánto facturó Café Central?"},
        headers=LA80,
    )
    assert res.status_code == 200
    body = res.json()
    # El LLM no puede obtener los datos porque la tool rechaza la llamada con forbidden
    tool_results = [call["result"] for call in body["tool_calls"]]
    assert any(
        r.get("status") == "error" and r.get("error", {}).get("code") == "forbidden"
        for r in tool_results
    )


def test_chat_empty_message_is_rejected(client: TestClient) -> None:
    res = client.post("/api/chat", json={"message": "   "}, headers=ADMIN)
    assert res.status_code == 422
