"""Configuración de la aplicación. Lee las variables del .env."""

from pydantic_settings import BaseSettings, SettingsConfigDict


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


settings = Settings()
