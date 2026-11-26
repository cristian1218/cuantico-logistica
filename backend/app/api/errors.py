"""Errores HTTP con formato uniforme `{error: {code, message}}` y sin fugas internas."""

from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.domain.errors import ConflictingEventError, DomainError, InconsistentEventsError

log = logging.getLogger("cuantico")


class ApiError(Exception):
    def __init__(
        self,
        status: int,
        code: str,
        message: str,
        headers: dict[str, str] | None = None,
    ) -> None:
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message
        self.headers = headers


def _body(
    code: str, message: str, details: list[dict[str, str]] | None = None
) -> dict[str, object]:
    error: dict[str, object] = {"code": code, "message": message}
    if details is not None:
        error["details"] = details
    return {"error": error}


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def _api_error(_: Request, exc: ApiError) -> JSONResponse:
        return JSONResponse(
            _body(exc.code, exc.message), status_code=exc.status, headers=exc.headers
        )

    @app.exception_handler(RequestValidationError)
    async def _validation(_: Request, exc: RequestValidationError) -> JSONResponse:
        # Solo ubicacion + mensaje: se omite `input` para no devolver al cliente (ni a logs)
        # el valor recibido, que podria ser grande o malicioso.
        details = [
            {"field": ".".join(str(p) for p in e["loc"]), "message": str(e["msg"])}
            for e in exc.errors()
        ]
        return JSONResponse(
            _body("validation_error", "La solicitud no es valida", details), status_code=422
        )

    @app.exception_handler(ConflictingEventError)
    async def _conflict(_: Request, exc: ConflictingEventError) -> JSONResponse:
        return JSONResponse(_body("conflicting_event", str(exc)), status_code=409)

    @app.exception_handler(InconsistentEventsError)
    async def _inconsistent(_: Request, exc: InconsistentEventsError) -> JSONResponse:
        return JSONResponse(_body("inconsistent_events", str(exc)), status_code=409)

    @app.exception_handler(DomainError)
    async def _domain(_: Request, exc: DomainError) -> JSONResponse:
        return JSONResponse(_body("domain_error", str(exc)), status_code=422)

    @app.exception_handler(StarletteHTTPException)
    async def _http(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        return JSONResponse(
            _body("http_error", str(exc.detail)), status_code=exc.status_code, headers=exc.headers
        )

    @app.exception_handler(Exception)
    async def _unexpected(request: Request, exc: Exception) -> JSONResponse:
        # El detalle va al log del servidor; el cliente solo ve un mensaje generico.
        log.error("error no controlado en %s %s", request.method, request.url.path, exc_info=exc)
        return JSONResponse(_body("internal_error", "Error interno del servidor"), status_code=500)
