"""SEC4: configuracion y secretos."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from app.config import ConfigError, Settings, parse_tokens
from app.main import create_app

REPO_ROOT = Path(__file__).resolve().parents[2]


def settings_with(**kw: str) -> Settings:
    return Settings(_env_file=None, **kw)  # type: ignore[call-arg]


def test_SEC4_app_refuses_to_start_without_tokens() -> None:
    with pytest.raises(ConfigError, match="API_TOKENS"):
        create_app(settings_with(api_tokens="", database_url="sqlite:///:memory:"))


@pytest.mark.parametrize(
    "raw",
    [
        "sin-dos-puntos",
        "tok-largo-1:",  # alcance vacio
        "corto:all",  # token debil (< 8 chars)
        ":all",
        "tok-largo-1:all;tok-largo-1:m-x",  # token duplicado
    ],
)
def test_SEC4_malformed_tokens_are_rejected(raw: str) -> None:
    with pytest.raises(ConfigError):
        parse_tokens(raw)


def test_parse_tokens_scopes() -> None:
    tokens = parse_tokens("tok-admin-01:all; tok-two-0002:m-a, m-b")
    admin, scoped = tokens["tok-admin-01"], tokens["tok-two-0002"]
    assert admin.merchant_ids is None
    assert admin.can_access("cualquiera")
    assert scoped.merchant_ids == frozenset({"m-a", "m-b"})
    assert scoped.can_access("m-a")
    assert not scoped.can_access("m-z")


def test_SEC4_only_sqlite_urls_supported() -> None:
    with pytest.raises(ConfigError):
        settings_with(api_tokens="tok-admin-01:all", database_url="postgres://x").sqlite_path()


def test_SEC4_empty_gemini_key_means_mock() -> None:
    assert settings_with(api_tokens="tok-admin-01:all", gemini_api_key="").gemini_api_key is None


def test_SEC4_env_is_gitignored() -> None:
    ignored = (REPO_ROOT / ".gitignore").read_text().splitlines()
    assert ".env" in ignored


SECRET_PATTERNS = [
    re.compile(r"AIza[0-9A-Za-z_\-]{30,}"),  # formato de API keys de Google
    re.compile(r"sk-[A-Za-z0-9]{32,}"),
    re.compile(r"""(?i)api[_-]?key\s*[=:]\s*["'][^"']{16,}["']"""),
]
SKIP_DIRS = {".git", ".venv", "node_modules", "__pycache__", ".pytest_cache", ".mypy_cache"}
SKIP_FILES = {".env"}  # local y gitignored; el resto del arbol si se escanea


def test_SEC4_no_hardcoded_secrets_in_repo() -> None:
    offenders: list[str] = []
    for path in REPO_ROOT.rglob("*"):
        if not path.is_file() or path.name in SKIP_FILES or SKIP_DIRS & set(path.parts):
            continue
        if path.suffix in {".db", ".png", ".jpg", ".docx", ".pyc"}:
            continue
        try:
            text = path.read_text(errors="ignore")
        except OSError:
            continue
        for pattern in SECRET_PATTERNS:
            if pattern.search(text):
                offenders.append(f"{path.relative_to(REPO_ROOT)} ~ {pattern.pattern[:20]}")
    assert not offenders, f"posibles secretos en el repo: {offenders}"
