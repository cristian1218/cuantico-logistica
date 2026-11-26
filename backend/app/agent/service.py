"""Servicio orquestador del agente conversacional (ReAct loop)."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from typing import Any

from app.agent.llm_client import GeminiLLMClient, LLMClient, MockLLMClient
from app.agent.tools import execute_tool
from app.config import Principal, Settings
from app.store.db import Database

MAX_AGENT_TURNS = 5


@dataclass(frozen=True)
class ToolCallRecord:
    name: str
    args: dict[str, Any]
    result: dict[str, Any]


@dataclass(frozen=True)
class AgentResponse:
    answer: str
    tool_calls: list[ToolCallRecord] = field(default_factory=list)


class AgentService:
    def __init__(
        self,
        settings: Settings,
        db: Database,
        llm_client: LLMClient | None = None,
    ) -> None:
        self.settings = settings
        self.db = db
        if llm_client is not None:
            self.llm = llm_client
        elif settings.gemini_api_key:
            self.llm = GeminiLLMClient(api_key=settings.gemini_api_key, model=settings.gemini_model)
        else:
            self.llm = MockLLMClient()

    def run_chat(
        self,
        conn: sqlite3.Connection,
        principal: Principal,
        user_message: str,
    ) -> AgentResponse:
        history: list[dict[str, Any]] = [{"role": "user", "text": user_message}]
        collected_tool_records: list[ToolCallRecord] = []

        for _ in range(MAX_AGENT_TURNS):
            turn = self.llm.step(history)

            if turn.tool_calls:
                # El modelo solicitó invocar una o varias herramientas
                tool_call_dicts = [{"name": tc.name, "args": tc.args} for tc in turn.tool_calls]
                history.append(
                    {
                        "role": "model",
                        "tool_calls": tool_call_dicts,
                    }
                )

                # Ejecutamos determinísticamente cada herramienta inyectando principal desde el servidor
                tool_responses: list[dict[str, Any]] = []
                for tc in turn.tool_calls:
                    result = execute_tool(conn, principal, tc.name, tc.args)
                    collected_tool_records.append(
                        ToolCallRecord(name=tc.name, args=tc.args, result=result)
                    )
                    tool_responses.append({"name": tc.name, "result": result})

                history.append(
                    {
                        "role": "tool",
                        "tool_responses": tool_responses,
                    }
                )
            elif turn.text:
                return AgentResponse(
                    answer=turn.text,
                    tool_calls=collected_tool_records,
                )
            else:
                break

        return AgentResponse(
            answer="No pude completar la consulta en el límite de turnos permitido.",
            tool_calls=collected_tool_records,
        )
