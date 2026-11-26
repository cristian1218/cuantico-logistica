"""Distancia geografica."""

from __future__ import annotations

from math import asin, cos, radians, sin, sqrt

EARTH_RADIUS_KM = 6371.0088  # radio medio IUGG


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Distancia en linea recta (S3), redondeada a metros (R4) para ser reproducible."""
    phi1, phi2 = radians(lat1), radians(lat2)
    dphi = phi2 - phi1
    dlmb = radians(lon2 - lon1)
    a = sin(dphi / 2) ** 2 + cos(phi1) * cos(phi2) * sin(dlmb / 2) ** 2
    return round(2 * EARTH_RADIUS_KM * asin(sqrt(a)), 3)
