"""Punto de entrada. Se usa como fabrica: `uvicorn app.main:create_app --factory`.

Al ser fabrica, importar este modulo (p. ej. en tests) no exige configuracion; arrancar el
servidor si, y falla con un mensaje claro si falta algo (SEC4).
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.agent.service import AgentService
from app.api.errors import register_error_handlers
from app.api.routes import router
from app.config import Settings, parse_tokens
from app.store.db import Database


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()
    tokens = parse_tokens(settings.api_tokens)  # ConfigError si falta o es invalido
    db = Database(settings.sqlite_path())
    db.init_schema()

    app = FastAPI(title="Cuantico Logistica", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.state.settings = settings
    app.state.tokens = tokens
    app.state.db = db
    app.state.agent_service = AgentService(settings=settings, db=db)
    register_error_handlers(app)
    app.include_router(router, prefix="/api")
    return app
