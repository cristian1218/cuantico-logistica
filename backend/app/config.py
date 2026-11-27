"""Configuracion y autenticacion por token con alcance (SEC3, SEC4).

Todo secreto llega por variables de entorno (o .env local, ignorado por git).
La aplicacion se niega a arrancar si falta lo obligatorio.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]
MIN_TOKEN_LENGTH = 8


class ConfigError(Exception):
    """Configuracion invalida o incompleta. El mensaje es apto para mostrar al operador."""


@dataclass(frozen=True)
class Principal:
    """Usuario autenticado. `merchant_ids=None` significa alcance global."""

    name: str
    merchant_ids: frozenset[str] | None

    def can_access(self, merchant_id: str) -> bool:
        return self.merchant_ids is None or merchant_id in self.merchant_ids


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=REPO_ROOT / ".env", extra="ignore")

    api_tokens: str = ""
    database_url: str = "sqlite:///./cuantico.db"
    gemini_api_key: str | None = None
    gemini_model: str = "gemini-3.5-flash"

    @field_validator("gemini_api_key")
    @classmethod
    def _empty_key_means_none(cls, value: str | None) -> str | None:
        return value or None

    def sqlite_path(self) -> str:
        prefix = "sqlite:///"
        if not self.database_url.startswith(prefix):
            raise ConfigError("DATABASE_URL: solo se soportan URLs sqlite:/// en esta version")
        return self.database_url[len(prefix) :]


def parse_tokens(raw: str) -> dict[str, Principal]:
    """Formato: `token:alcance;token:alcance`, alcance = `all` o ids separados por coma."""
    tokens: dict[str, Principal] = {}
    entries = [e.strip() for e in raw.split(";") if e.strip()]
    if not entries:
        raise ConfigError(
            "API_TOKENS esta vacio. Define al menos un token en .env "
            "(ver .env.example), p. ej. API_TOKENS=mi-token-largo:all"
        )
    for index, entry in enumerate(entries, start=1):
        token, sep, scope = (part.strip() for part in entry.partition(":"))
        if not sep or not token or not scope:
            raise ConfigError(f"API_TOKENS: entrada #{index} invalida; usa token:alcance")
        if len(token) < MIN_TOKEN_LENGTH:
            raise ConfigError(
                f"API_TOKENS: el token #{index} es demasiado corto (minimo {MIN_TOKEN_LENGTH})"
            )
        if token in tokens:
            raise ConfigError(f"API_TOKENS: token duplicado en la entrada #{index}")
        if scope == "all":
            merchant_ids: frozenset[str] | None = None
        else:
            ids = frozenset(s.strip() for s in scope.split(",") if s.strip())
            if not ids:
                raise ConfigError(f"API_TOKENS: alcance vacio en la entrada #{index}")
            merchant_ids = ids
        # El nombre NO deriva del token: nunca se registra ni se expone el secreto.
        tokens[token] = Principal(name=f"user-{index}", merchant_ids=merchant_ids)
    return tokens
