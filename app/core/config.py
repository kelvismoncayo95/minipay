"""Configuración de la aplicación. Lee las variables del .env o del entorno."""

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def normalize_database_url(url: str) -> str:
    """Los hostings suelen dar `postgres://...`; SQLAlchemy + psycopg 3 necesita
    `postgresql+psycopg://...`."""
    for prefijo in ("postgres://", "postgresql://"):
        if url.startswith(prefijo):
            return "postgresql+psycopg://" + url[len(prefijo):]
    return url


class Settings(BaseSettings):
    """Configuración de minipay. Los valores vienen del .env o del entorno."""

    database_url: str
    redis_url: str
    jwt_secret: str
    jwt_expire_minutes: int = 60

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @field_validator("database_url")
    @classmethod
    def _normalizar(cls, valor: str) -> str:
        return normalize_database_url(valor)


settings = Settings()
