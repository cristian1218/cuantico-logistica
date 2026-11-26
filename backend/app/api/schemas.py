"""Esquemas HTTP (entrada estricta, salida explicita)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator

from app.domain.models import CURRENCY, Event, EventType
from app.store.repository import DeliveryRecord

_ID = Field(min_length=1, max_length=64)


class EventIn(BaseModel):
    """Evento de entrega. `extra=forbid`: campos desconocidos se rechazan, no se ignoran."""

    model_config = ConfigDict(extra="forbid")

    event_id: str = _ID
    delivery_id: str = _ID
    merchant_id: str = _ID
    courier_id: str = _ID
    type: EventType
    occurred_at: AwareDatetime  # sin zona horaria => 422 (el instante seria ambiguo)
    lat: float | None = Field(default=None, ge=-90, le=90)
    lon: float | None = Field(default=None, ge=-180, le=180)
    address: str | None = Field(default=None, max_length=200)

    def to_domain(self) -> Event:
        return Event(
            event_id=self.event_id,
            delivery_id=self.delivery_id,
            merchant_id=self.merchant_id,
            courier_id=self.courier_id,
            type=self.type,
            occurred_at=self.occurred_at,
            lat=self.lat,
            lon=self.lon,
            address=self.address,
        )


class DeliveryOut(BaseModel):
    delivery_id: str
    merchant_id: str
    courier_id: str
    status: str
    cost_status: str
    cost_cents: int | None
    currency: str = CURRENCY
    closed_at: str | None
    address: str | None
    breakdown: dict[str, Any] | None
    anomalies: list[str]

    @classmethod
    def from_record(cls, record: DeliveryRecord) -> DeliveryOut:
        return cls(**record.__dict__)


class IngestOut(BaseModel):
    duplicate: bool
    delivery: DeliveryOut


class MerchantTotalsOut(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    merchant_id: str
    merchant_name: str
    from_: datetime = Field(serialization_alias="from")
    to: datetime
    deliveries: int
    delivered: int
    failed: int
    total_cents: int
    currency: str = CURRENCY
    pending_cost_deliveries: int


class CourierStatusOut(BaseModel):
    courier_id: str
    total: int
    by_status: dict[str, int]


class SearchHitOut(BaseModel):
    delivery_id: str
    merchant_id: str
    merchant_name: str
    courier_id: str
    courier_name: str | None
    address: str | None
    status: str
    cost_status: str
    cost_cents: int | None


class SearchOut(BaseModel):
    query: str
    count: int
    results: list[SearchHitOut]


class ChatIn(BaseModel):
    message: str = Field(min_length=1, max_length=2000)

    @field_validator("message")
    @classmethod
    def _non_empty_message(cls, v: str) -> str:
        trimmed = v.strip()
        if not trimmed:
            raise ValueError("El mensaje no puede estar vacío")
        return trimmed


class ToolCallOut(BaseModel):
    name: str
    args: dict[str, Any]
    result: dict[str, Any]


class ChatOut(BaseModel):
    answer: str
    tool_calls: list[ToolCallOut]
