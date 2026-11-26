"""Conexion y esquema SQLite.

Modelo: `events` es un log append-only (fuente de verdad); `deliveries` es una proyeccion
derivada que se recalcula desde los eventos en cada ingesta (ver repository.ingest_event).
"""

from __future__ import annotations

import sqlite3

SCHEMA = """
CREATE TABLE IF NOT EXISTS merchants (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    timezone TEXT NOT NULL,
    base_fee_cents INTEGER NOT NULL CHECK (base_fee_cents >= 0),
    per_km_cents INTEGER NOT NULL CHECK (per_km_cents >= 0),
    notes TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS couriers (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS events (
    event_id TEXT PRIMARY KEY,
    delivery_id TEXT NOT NULL,
    merchant_id TEXT NOT NULL REFERENCES merchants(id),
    courier_id TEXT NOT NULL,
    type TEXT NOT NULL,
    occurred_at TEXT NOT NULL,
    lat REAL,
    lon REAL,
    address TEXT,
    received_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_events_delivery ON events(delivery_id);

CREATE TABLE IF NOT EXISTS deliveries (
    delivery_id TEXT PRIMARY KEY,
    merchant_id TEXT NOT NULL REFERENCES merchants(id),
    courier_id TEXT NOT NULL,
    status TEXT NOT NULL,
    cost_status TEXT NOT NULL,
    cost_cents INTEGER,
    closed_at TEXT,
    address TEXT,
    breakdown_json TEXT,
    anomalies_json TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_deliveries_merchant_closed ON deliveries(merchant_id, closed_at);
CREATE INDEX IF NOT EXISTS idx_deliveries_courier_status ON deliveries(courier_id, status);
"""


class Database:
    def __init__(self, path: str) -> None:
        self.path = path

    def connect(self) -> sqlite3.Connection:
        # isolation_level=None: control manual de transacciones (BEGIN IMMEDIATE).
        # check_same_thread=False: FastAPI puede abrir y usar la conexion en hilos distintos
        # del pool, pero cada conexion pertenece a una sola peticion a la vez.
        conn = sqlite3.connect(self.path, isolation_level=None, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA busy_timeout = 5000")
        return conn

    def init_schema(self) -> None:
        conn = self.connect()
        try:
            conn.execute("PRAGMA journal_mode = WAL")
            conn.executescript(SCHEMA)
        finally:
            conn.close()
