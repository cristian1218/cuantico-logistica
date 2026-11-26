"""Modelos del dominio. Puros: sin I/O ni dependencias de framework."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

CURRENCY = "COP"  # S10: moneda unica; montos en centavos enteros


class EventType(str, Enum):
    CREADA = "creada"
    ASIGNADA = "asignada"
    RECOGIDA = "recogida"
    EN_RUTA = "en_ruta"
    ENTREGADA = "entregada"
    FALLIDA = "fallida"


# R1: orden del ciclo de vida. FALLIDA queda fuera: no es un paso del ciclo normal.
LIFECYCLE_ORDER: tuple[EventType, ...] = (
    EventType.CREADA,
    EventType.ASIGNADA,
    EventType.RECOGIDA,
    EventType.EN_RUTA,
    EventType.ENTREGADA,
)
_COORDINATE_TYPES = {EventType.RECOGIDA, EventType.ENTREGADA}


@dataclass(frozen=True)
class Event:
    event_id: str
    delivery_id: str
    merchant_id: str
    courier_id: str
    type: EventType
    occurred_at: datetime
    lat: float | None = None
    lon: float | None = None
    address: str | None = None  # S9: solo para busqueda; no participa en el costo

    def __post_init__(self) -> None:
        if not self.event_id:
            raise ValueError("event_id es obligatorio")  # S6
        if self.occurred_at.tzinfo is None or self.occurred_at.utcoffset() is None:
            raise ValueError("occurred_at debe incluir zona horaria")
        # Se normaliza a UTC: toda la logica trabaja con instantes inequivocos.
        object.__setattr__(self, "occurred_at", self.occurred_at.astimezone(UTC))
        if self.type in _COORDINATE_TYPES and (self.lat is None or self.lon is None):
            raise ValueError(f"'{self.type.value}' requiere lat y lon")
        if self.lat is not None and not -90.0 <= self.lat <= 90.0:
            raise ValueError("lat fuera de rango")
        if self.lon is not None and not -180.0 <= self.lon <= 180.0:
            raise ValueError("lon fuera de rango")


@dataclass(frozen=True)
class Tariff:
    base_fee_cents: int
    per_km_cents: int
    timezone: str

    def __post_init__(self) -> None:
        if self.base_fee_cents < 0 or self.per_km_cents < 0:
            raise ValueError("las tarifas no pueden ser negativas")
        try:
            ZoneInfo(self.timezone)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise ValueError(f"zona horaria invalida: {self.timezone}") from exc


@dataclass(frozen=True)
class CostBreakdown:
    """R12: desglose auditable de como se calculo un costo."""

    outcome: str  # "entregada" | "fallida"
    base_fee_cents: int
    per_km_cents: int
    timezone: str
    distance_km: float | None
    distance_charge_cents: int
    night_surcharge_percent: int
    night_surcharge_cents: int
    failed_percent: int | None
    local_delivery_time: str | None
    total_cents: int
    event_ids_used: tuple[str, ...]
    algorithm_version: str


@dataclass(frozen=True)
class DeliveryState:
    delivery_id: str
    merchant_id: str
    courier_id: str
    status: EventType
    cost_status: str  # "calculado" | "pendiente"
    cost_cents: int | None
    breakdown: CostBreakdown | None
    closed_at: datetime | None  # instante de cierre (entregada o fallida) para S4
    anomalies: tuple[str, ...]
