"""Carga idempotente del dataset de ejemplo: `make seed` / `python -m app.seed`.

Los eventos pasan por el mismo `ingest_event` que usa la API: el seed no tiene logica propia
de calculo, asi que ejercita idempotencia y desorden igual que el trafico real (el fixture
incluye un evento duplicado y una entrega con eventos desordenados a proposito).
"""

from __future__ import annotations

import json
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.api.schemas import EventIn
from app.config import REPO_ROOT, Settings
from app.store import repository as repo
from app.store.db import Database

FIXTURES_DIR = REPO_ROOT / "fixtures"


@dataclass(frozen=True)
class SeedSummary:
    merchants: int
    couriers: int
    events_new: int
    events_duplicate: int


def _read(name: str, directory: Path) -> list[dict[str, Any]]:
    data: list[dict[str, Any]] = json.loads((directory / name).read_text(encoding="utf-8"))
    return data


def load_fixtures(db: Database, directory: Path = FIXTURES_DIR) -> SeedSummary:
    merchants = _read("merchants.json", directory)
    couriers = _read("couriers.json", directory)
    events = _read("events.json", directory)
    new = duplicate = 0
    with closing(db.connect()) as conn:
        for m in merchants:
            repo.upsert_merchant(conn, repo.MerchantRow(**m))
        for c in couriers:
            repo.upsert_courier(conn, c["id"], c["name"])
        for raw in events:
            result = repo.ingest_event(conn, EventIn.model_validate(raw).to_domain())
            if result.duplicate:
                duplicate += 1
            else:
                new += 1
    return SeedSummary(len(merchants), len(couriers), new, duplicate)


def main() -> None:
    settings = Settings()
    db = Database(settings.sqlite_path())
    db.init_schema()
    s = load_fixtures(db)
    print(
        f"Seed OK: {s.merchants} comercios, {s.couriers} mensajeros, "
        f"{s.events_new} eventos nuevos, {s.events_duplicate} duplicados ignorados."
    )


if __name__ == "__main__":
    main()
