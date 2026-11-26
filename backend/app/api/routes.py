"""Rutas HTTP. Cada ruta: autentica, autoriza por alcance, delega en dominio/store."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query, Request, Response
from pydantic import AwareDatetime

from app.api.deps import Conn, CurrentUser
from app.api.errors import ApiError
from app.api.schemas import (
    ChatIn,
    ChatOut,
    CourierStatusOut,
    DeliveryOut,
    EventIn,
    IngestOut,
    MerchantTotalsOut,
    SearchHitOut,
    SearchOut,
    ToolCallOut,
)
from app.domain.models import EventType
from app.store import queries
from app.store import repository as repo

router = APIRouter()


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.post("/events", response_model=IngestOut, status_code=201)
def ingest(payload: EventIn, user: CurrentUser, conn: Conn, response: Response) -> IngestOut:
    try:
        event = payload.to_domain()
    except ValueError as exc:  # p. ej. recogida sin coordenadas
        raise ApiError(422, "validation_error", str(exc)) from exc
    # Autorizacion ANTES de tocar la BD: un token acotado no puede ni sondear otros comercios.
    if not user.can_access(event.merchant_id):
        raise ApiError(403, "forbidden", "Sin acceso a este comercio")
    try:
        result = repo.ingest_event(conn, event)
    except repo.UnknownMerchantError as exc:
        raise ApiError(422, "unknown_merchant", "El comercio no existe") from exc
    if result.duplicate:
        response.status_code = 200  # R7: duplicado reconocido, sin efectos
    record = repo.get_delivery(conn, result.delivery_id)
    assert record is not None
    return IngestOut(duplicate=result.duplicate, delivery=DeliveryOut.from_record(record))


# /deliveries/search debe declararse antes que /deliveries/{delivery_id}
@router.get("/deliveries/search", response_model=SearchOut)
def search(
    q: Annotated[str, Query(min_length=1, max_length=100)], user: CurrentUser, conn: Conn
) -> SearchOut:
    hits = queries.search_deliveries(conn, q, user.merchant_ids)
    return SearchOut(query=q, count=len(hits), results=[SearchHitOut(**h.__dict__) for h in hits])


@router.get("/deliveries/{delivery_id}", response_model=DeliveryOut)
def delivery_detail(delivery_id: str, user: CurrentUser, conn: Conn) -> DeliveryOut:
    record = repo.get_delivery(conn, delivery_id)
    # Fuera de alcance => 404 igual que inexistente: no se revela que la entrega existe.
    if record is None or not user.can_access(record.merchant_id):
        raise ApiError(404, "not_found", "Entrega no encontrada")
    return DeliveryOut.from_record(record)


@router.get(
    "/reports/merchant-totals", response_model=MerchantTotalsOut, response_model_by_alias=True
)
def merchant_totals(
    merchant_id: Annotated[str, Query(min_length=1, max_length=64)],
    from_: Annotated[AwareDatetime, Query(alias="from")],
    to: AwareDatetime,
    user: CurrentUser,
    conn: Conn,
) -> MerchantTotalsOut:
    if not user.can_access(merchant_id):
        raise ApiError(403, "forbidden", "Sin acceso a este comercio")
    if from_ >= to:
        raise ApiError(422, "validation_error", "'from' debe ser anterior a 'to'")
    merchant = repo.get_merchant(conn, merchant_id)
    if merchant is None:
        raise ApiError(404, "not_found", "Comercio no encontrado")
    totals = queries.merchant_totals(conn, merchant_id, from_, to)
    return MerchantTotalsOut(
        merchant_id=merchant.id, merchant_name=merchant.name, from_=from_, to=to, **totals.__dict__
    )


@router.get("/reports/courier-status", response_model=CourierStatusOut)
def courier_status(
    courier_id: Annotated[str, Query(min_length=1, max_length=64)], user: CurrentUser, conn: Conn
) -> CourierStatusOut:
    # El conteo se limita al alcance del usuario: no puede ver entregas de otros comercios.
    counts = queries.courier_status_counts(conn, courier_id, user.merchant_ids)
    by_status = {t.value: counts.get(t.value, 0) for t in EventType}  # forma estable
    return CourierStatusOut(
        courier_id=courier_id, total=sum(by_status.values()), by_status=by_status
    )


@router.post("/chat", response_model=ChatOut)
def chat(
    payload: ChatIn,
    request: Request,
    user: CurrentUser,
    conn: Conn,
) -> ChatOut:
    agent_service = request.app.state.agent_service
    response = agent_service.run_chat(conn, user, payload.message)
    return ChatOut(
        answer=response.answer,
        tool_calls=[
            ToolCallOut(name=tc.name, args=tc.args, result=tc.result) for tc in response.tool_calls
        ],
    )
