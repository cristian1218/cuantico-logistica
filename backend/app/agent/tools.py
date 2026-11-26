"""Herramientas deterministas para el agente conversacional (SEC1, SEC2, SEC3).

El LLM NUNCA calcula ni agrega datos por su cuenta: llama a estas herramientas.
El contexto de autorización (`principal`) es inyectado exclusivamente por el servidor,
por lo que el LLM no puede eludir el alcance asignado al usuario.
"""

from __future__ import annotations

import re
import sqlite3
from datetime import UTC, datetime
from typing import Any, cast

from google.genai import types

from app.config import Principal
from app.domain.models import CURRENCY
from app.store import queries
from app.store import repository as repo

# Control de longitud y caracteres para notas no confiables
MAX_NOTES_LENGTH = 500


def sanitize_untrusted_text(text: str) -> str:
    """Remueve caracteres de control extraños y limita el tamaño (SEC2)."""
    # Remueve caracteres de control ASCII excepto \n, \r, \t
    cleaned = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)
    if len(cleaned) > MAX_NOTES_LENGTH:
        return cleaned[:MAX_NOTES_LENGTH] + "... [truncado]"
    return cleaned


def get_merchant_totals_tool(
    conn: sqlite3.Connection,
    principal: Principal,
    merchant_id: str,
    from_date: str,
    to_date: str,
) -> dict[str, Any]:
    """Consulta totales facturados y entregas de un comercio en un rango de fechas."""
    if not principal.can_access(merchant_id):
        return {
            "status": "error",
            "error": {
                "code": "forbidden",
                "message": f"No tienes autorización para acceder a los datos del comercio '{merchant_id}'",
            },
        }

    try:
        dt_from = datetime.fromisoformat(from_date)
        dt_to = datetime.fromisoformat(to_date)
    except ValueError as exc:
        return {
            "status": "error",
            "error": {"code": "invalid_date", "message": f"Formato de fecha inválido: {exc}"},
        }

    if dt_from.tzinfo is None:
        dt_from = dt_from.replace(tzinfo=UTC)
    if dt_to.tzinfo is None:
        dt_to = dt_to.replace(tzinfo=UTC)

    merchant = repo.get_merchant(conn, merchant_id)
    if merchant is None:
        return {
            "status": "error",
            "error": {"code": "not_found", "message": f"Comercio '{merchant_id}' no encontrado"},
        }

    res = queries.merchant_totals(conn, merchant_id, dt_from, dt_to)
    return {
        "status": "ok",
        "data": {
            "merchant_id": merchant.id,
            "merchant_name": merchant.name,
            "from": dt_from.isoformat(),
            "to": dt_to.isoformat(),
            "deliveries": res.deliveries,
            "delivered": res.delivered,
            "failed": res.failed,
            "total_cents": res.total_cents,
            "currency": CURRENCY,
            "pending_cost_deliveries": res.pending_cost_deliveries,
        },
    }


def get_courier_status_tool(
    conn: sqlite3.Connection,
    principal: Principal,
    courier_id: str,
) -> dict[str, Any]:
    """Consulta entregas agrupadas por estado para un mensajero dado (acotado al alcance del usuario)."""
    counts = queries.courier_status_counts(conn, courier_id, principal.merchant_ids)
    total = sum(counts.values())
    return {
        "status": "ok",
        "data": {
            "courier_id": courier_id,
            "total": total,
            "by_status": counts,
        },
    }


def search_deliveries_tool(
    conn: sqlite3.Connection,
    principal: Principal,
    query: str,
) -> dict[str, Any]:
    """Buscador seguro de texto libre sobre entregas, comercios y mensajeros (SEC1, SEC3)."""
    hits = queries.search_deliveries(conn, query, principal.merchant_ids)
    return {
        "status": "ok",
        "data": {
            "query": query,
            "count": len(hits),
            "results": [
                {
                    "delivery_id": h.delivery_id,
                    "merchant_id": h.merchant_id,
                    "merchant_name": h.merchant_name,
                    "courier_id": h.courier_id,
                    "courier_name": h.courier_name,
                    "address": h.address,
                    "status": h.status,
                    "cost_status": h.cost_status,
                    "cost_cents": h.cost_cents,
                    "currency": CURRENCY,
                }
                for h in hits
            ],
        },
    }


def get_delivery_detail_tool(
    conn: sqlite3.Connection,
    principal: Principal,
    delivery_id: str,
) -> dict[str, Any]:
    """Detalle completo de una entrega incluyendo desglose auditable (SEC3)."""
    record = repo.get_delivery(conn, delivery_id)
    if record is None or not principal.can_access(record.merchant_id):
        return {
            "status": "error",
            "error": {"code": "not_found", "message": f"Entrega '{delivery_id}' no encontrada"},
        }

    return {
        "status": "ok",
        "data": {
            "delivery_id": record.delivery_id,
            "merchant_id": record.merchant_id,
            "courier_id": record.courier_id,
            "status": record.status,
            "cost_status": record.cost_status,
            "cost_cents": record.cost_cents,
            "currency": CURRENCY,
            "closed_at": record.closed_at,
            "address": record.address,
            "breakdown": record.breakdown,
            "anomalies": record.anomalies,
        },
    }


def get_merchant_info_tool(
    conn: sqlite3.Connection,
    principal: Principal,
    merchant_id: str,
) -> dict[str, Any]:
    """Información general de un comercio.

    SEC2: Las notas son dato no confiable (provienen de usuarios/sistemas externos).
    Se sanitizan y se devuelven encapsuladas en etiquetas delimitadas para que el modelo
    las interprete estrictamente como datos pasivos y nunca como instrucciones.
    """
    if not principal.can_access(merchant_id):
        return {
            "status": "error",
            "error": {
                "code": "forbidden",
                "message": f"No tienes autorización para acceder a los datos del comercio '{merchant_id}'",
            },
        }

    merchant = repo.get_merchant(conn, merchant_id)
    if merchant is None:
        return {
            "status": "error",
            "error": {"code": "not_found", "message": f"Comercio '{merchant_id}' no encontrado"},
        }

    sanitized_notes = sanitize_untrusted_text(merchant.notes)
    wrapped_notes = f"<untrusted_merchant_notes>\n{sanitized_notes}\n</untrusted_merchant_notes>"

    return {
        "status": "ok",
        "data": {
            "merchant_id": merchant.id,
            "merchant_name": merchant.name,
            "timezone": merchant.timezone,
            "base_fee_cents": merchant.base_fee_cents,
            "per_km_cents": merchant.per_km_cents,
            "currency": CURRENCY,
            "notes": wrapped_notes,
            "is_untrusted_content": True,
        },
    }


# Mapeo de despacho de herramientas
TOOL_REGISTRY = {
    "get_merchant_totals": get_merchant_totals_tool,
    "get_courier_status": get_courier_status_tool,
    "search_deliveries": search_deliveries_tool,
    "get_delivery_detail": get_delivery_detail_tool,
    "get_merchant_info": get_merchant_info_tool,
}


def execute_tool(
    conn: sqlite3.Connection,
    principal: Principal,
    name: str,
    arguments: dict[str, Any],
) -> dict[str, Any]:
    fn = TOOL_REGISTRY.get(name)
    if fn is None:
        return {
            "status": "error",
            "error": {"code": "unknown_tool", "message": f"Herramienta desconocida: {name}"},
        }
    try:
        res = fn(conn, principal, **arguments)  # type: ignore[operator]
        return cast(dict[str, Any], res)
    except Exception as exc:  # noqa: BLE001 - resguardo para que un fallo en tool no tumbe el servidor
        return {
            "status": "error",
            "error": {"code": "tool_execution_error", "message": str(exc)},
        }


# Declaraciones para Google Gemini / Tool schema
GEMINI_FUNCTION_DECLARATIONS = [
    types.FunctionDeclaration(
        name="get_merchant_totals",
        description="Consulta totales facturados y número de entregas de un comercio en un rango de fechas.",
        parameters=types.Schema(
            type=types.Type.OBJECT,
            properties={
                "merchant_id": types.Schema(
                    type=types.Type.STRING,
                    description="Identificador único del comercio (ej. 'm-la80')",
                ),
                "from_date": types.Schema(
                    type=types.Type.STRING,
                    description="Fecha inicio en ISO-8601 (ej. '2026-11-16T00:00:00Z')",
                ),
                "to_date": types.Schema(
                    type=types.Type.STRING,
                    description="Fecha fin en ISO-8601 (ej. '2026-11-23T00:00:00Z')",
                ),
            },
            required=["merchant_id", "from_date", "to_date"],
        ),
    ),
    types.FunctionDeclaration(
        name="get_courier_status",
        description="Consulta las entregas agrupadas por estado (entregada, fallida, en_ruta, etc.) para un mensajero.",
        parameters=types.Schema(
            type=types.Type.OBJECT,
            properties={
                "courier_id": types.Schema(
                    type=types.Type.STRING,
                    description="Identificador único del mensajero (ej. 'c-ana')",
                ),
            },
            required=["courier_id"],
        ),
    ),
    types.FunctionDeclaration(
        name="search_deliveries",
        description="Buscador de entregas por texto libre (nombre de comercio, mensajero o dirección).",
        parameters=types.Schema(
            type=types.Type.OBJECT,
            properties={
                "query": types.Schema(
                    type=types.Type.STRING,
                    description="Término de búsqueda (ej. 'Calle 80', 'Pedro')",
                ),
            },
            required=["query"],
        ),
    ),
    types.FunctionDeclaration(
        name="get_delivery_detail",
        description="Consulta el detalle y estado de una entrega específica por su ID.",
        parameters=types.Schema(
            type=types.Type.OBJECT,
            properties={
                "delivery_id": types.Schema(
                    type=types.Type.STRING,
                    description="Identificador único de la entrega (ej. 'd1')",
                ),
            },
            required=["delivery_id"],
        ),
    ),
    types.FunctionDeclaration(
        name="get_merchant_info",
        description="Consulta la información básica y notas de operación de un comercio.",
        parameters=types.Schema(
            type=types.Type.OBJECT,
            properties={
                "merchant_id": types.Schema(
                    type=types.Type.STRING, description="Identificador del comercio (ej. 'm-la80')"
                ),
            },
            required=["merchant_id"],
        ),
    ),
]
