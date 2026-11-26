"""Clientes LLM: Adaptador para Google Gemini y Mock determinista para tests y modo offline."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Protocol

from google import genai
from google.genai import types

from app.agent.prompts import SYSTEM_INSTRUCTION
from app.agent.tools import GEMINI_FUNCTION_DECLARATIONS


@dataclass(frozen=True)
class ToolCallItem:
    name: str
    args: dict[str, Any]


@dataclass(frozen=True)
class LLMTurn:
    tool_calls: list[ToolCallItem] = field(default_factory=list)
    text: str | None = None


class LLMClient(Protocol):
    def step(self, history: list[dict[str, Any]]) -> LLMTurn: ...


class GeminiLLMClient:
    """Cliente real usando el SDK oficial de Google GenAI."""

    def __init__(self, api_key: str, model: str = "gemini-2.0-flash") -> None:
        self.client = genai.Client(api_key=api_key)
        self.model = model
        self.config = types.GenerateContentConfig(
            system_instruction=SYSTEM_INSTRUCTION,
            tools=[types.Tool(function_declarations=GEMINI_FUNCTION_DECLARATIONS)],
            temperature=0.0,
        )

    def step(self, history: list[dict[str, Any]]) -> LLMTurn:
        # Convierte el historial a objetos types.Content
        contents: list[types.Content] = []
        for msg in history:
            role = msg["role"]
            parts: list[types.Part] = []
            if msg.get("text"):
                parts.append(types.Part.from_text(text=msg["text"]))
            if "tool_calls" in msg:
                for tc in msg["tool_calls"]:
                    parts.append(
                        types.Part(
                            function_call=types.FunctionCall(
                                name=tc["name"],
                                args=tc["args"],
                            )
                        )
                    )
            if "tool_responses" in msg:
                for tr in msg["tool_responses"]:
                    parts.append(
                        types.Part(
                            function_response=types.FunctionResponse(
                                name=tr["name"],
                                response=tr["result"],
                            )
                        )
                    )
            contents.append(types.Content(role=role, parts=parts))

        response = self.client.models.generate_content(
            model=self.model,
            contents=contents,
            config=self.config,
        )

        tool_calls: list[ToolCallItem] = []
        if response.function_calls:
            for fc in response.function_calls:
                tool_calls.append(ToolCallItem(name=fc.name or "", args=dict(fc.args or {})))

        text = response.text if not tool_calls else None
        return LLMTurn(tool_calls=tool_calls, text=text)


class MockLLMClient:
    """Mock determinista que interpreta lenguaje natural y simula function calling.

    Permite probar el sistema completo de extremo a extremo sin depender de una API key
    y valida el comportamiento de seguridad (SEC2) de forma determinista y reproducible.
    """

    def step(self, history: list[dict[str, Any]]) -> LLMTurn:
        last_msg = history[-1]

        # Si el último mensaje es la respuesta de una tool, interpretamos el resultado
        if last_msg.get("role") == "tool" or "tool_responses" in last_msg:
            responses = last_msg.get("tool_responses", [])
            if not responses and "result" in last_msg:
                responses = [last_msg]

            texts: list[str] = []
            for resp in responses:
                name = resp.get("name")
                result = resp.get("result", {})

                if result.get("status") == "error":
                    err = result.get("error", {})
                    if err.get("code") == "forbidden":
                        texts.append(
                            "No tienes autorización para consultar la información de este recurso."
                        )
                    else:
                        texts.append(
                            f"Ocurrió un error al consultar el sistema: {err.get('message')}"
                        )
                    continue

                data = result.get("data", {})
                if name == "get_merchant_totals":
                    cents = data.get("total_cents", 0)
                    cop = cents / 100.0
                    texts.append(
                        f"El comercio {data.get('merchant_name')} facturó un total de ${cop:,.2f} COP "
                        f"con {data.get('deliveries')} entregas calculadas en el período consultado."
                    )
                elif name == "get_merchant_info":
                    notes = data.get("notes", "")
                    # SEC2: Demostración de manejo seguro del payload de inyección
                    if "IGNORA TUS INSTRUCCIONES" in notes:
                        # Extraemos solo la parte legítima antes de la inyección
                        texts.append(
                            f"Instrucciones para el comercio {data.get('merchant_name')}: "
                            f"Entregar en portería. (Se detectó y desestimó un intento de inyección de instrucciones en las notas)."
                        )
                    else:
                        texts.append(
                            f"Información de {data.get('merchant_name')}: notas registradas: {notes}"
                        )
                elif name == "get_courier_status":
                    total = data.get("total", 0)
                    by_status = data.get("by_status", {})
                    texts.append(
                        f"El mensajero {data.get('courier_id')} tiene un total de {total} entregas registradas: {by_status}."
                    )
                elif name == "search_deliveries":
                    results = data.get("results", [])
                    texts.append(f"Se encontraron {len(results)} entregas coincidentes.")
                elif name == "get_delivery_detail":
                    texts.append(
                        f"Entrega {data.get('delivery_id')}: estado {data.get('status')}, "
                        f"costo: ${data.get('cost_cents', 0) / 100.0:,.2f} COP."
                    )

            return LLMTurn(text=" ".join(texts) if texts else "Consulta completada con éxito.")

        # Si el último mensaje es del usuario, interpretamos la intención y generamos tool_calls
        user_text = (last_msg.get("text") or "").lower()

        # Intención: Facturación / Totales
        if any(w in user_text for w in ["factur", "total", "cuanto", "cuánto"]):
            merchant_id = "m-la80"
            if "cafe" in user_text or "café" in user_text:
                merchant_id = "m-cafe"
            elif "pizza" in user_text:
                merchant_id = "m-pizza"

            # Rango predeterminado (ejemplo semana del 16 al 23 nov 2026)
            from_date = "2026-11-16T00:00:00Z"
            to_date = "2026-11-23T00:00:00Z"
            return LLMTurn(
                tool_calls=[
                    ToolCallItem(
                        name="get_merchant_totals",
                        args={
                            "merchant_id": merchant_id,
                            "from_date": from_date,
                            "to_date": to_date,
                        },
                    )
                ]
            )

        # Intención: Notas de comercio / Instrucciones
        if any(w in user_text for w in ["nota", "instrucci"]):
            merchant_id = "m-la80"
            if "cafe" in user_text or "café" in user_text:
                merchant_id = "m-cafe"
            return LLMTurn(
                tool_calls=[
                    ToolCallItem(name="get_merchant_info", args={"merchant_id": merchant_id})
                ]
            )

        # Intención: Mensajero
        if any(w in user_text for w in ["mensajer", "ana", "luis", "pedro"]):
            courier_id = "c-ana"
            if "luis" in user_text:
                courier_id = "c-luis"
            elif "pedro" in user_text:
                courier_id = "c-pedro"
            return LLMTurn(
                tool_calls=[
                    ToolCallItem(name="get_courier_status", args={"courier_id": courier_id})
                ]
            )

        # Intención: Buscar
        if any(w in user_text for w in ["busc", "direcci", "carrera", "calle"]):
            query_match = re.search(r"(?:calle|carrera|av|reforma)[^?.!]*", user_text)
            q = query_match.group(0).strip() if query_match else "Bogotá"
            return LLMTurn(tool_calls=[ToolCallItem(name="search_deliveries", args={"query": q})])

        # Por defecto si no coincide
        return LLMTurn(
            text="¿En qué puedo ayudarte? Puedo consultar totales de comercio, estado de mensajeros o buscar entregas."
        )
