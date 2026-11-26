"""Dependencias de FastAPI: autenticacion y conexion a BD."""

from __future__ import annotations

import hmac
import sqlite3
from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends, Header, Request

from app.api.errors import ApiError
from app.config import Principal


def get_conn(request: Request) -> Iterator[sqlite3.Connection]:
    conn = request.app.state.db.connect()
    try:
        yield conn
    finally:
        conn.close()


def get_principal(
    request: Request, authorization: Annotated[str | None, Header()] = None
) -> Principal:
    """SEC3: Bearer token -> Principal con alcance. El alcance lo fija el servidor."""
    unauthorized = ApiError(
        401, "unauthorized", "Token ausente o invalido", {"WWW-Authenticate": "Bearer"}
    )
    if not authorization:
        raise unauthorized
    scheme, _, presented = authorization.partition(" ")
    if scheme.lower() != "bearer" or not presented:
        raise unauthorized
    found: Principal | None = None
    # Se recorren todos los tokens y se compara en tiempo constante: sin salida temprana
    # que filtre por timing cual prefijo coincide.
    for token, principal in request.app.state.tokens.items():
        if hmac.compare_digest(token.encode(), presented.strip().encode()):
            found = principal
    if found is None:
        raise unauthorized
    return found


CurrentUser = Annotated[Principal, Depends(get_principal)]
Conn = Annotated[sqlite3.Connection, Depends(get_conn)]
