"""Errores del dominio. La capa API los traduce a codigos HTTP."""


class DomainError(Exception):
    pass


class ConflictingEventError(DomainError):
    """R7: mismo event_id con contenido distinto."""


class InconsistentEventsError(DomainError):
    """S7: eventos de una misma entrega con delivery/merchant/courier distintos."""
