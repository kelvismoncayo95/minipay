"""Tests de configuración para producción (paso 14)."""

import pytest

from app.core.config import normalize_database_url


@pytest.mark.parametrize(
    "entrada",
    [
        "postgres://u:p@host:5432/db",
        "postgresql://u:p@host:5432/db",
        "postgresql+psycopg://u:p@host:5432/db",
    ],
)
def test_url_de_la_base_se_normaliza(entrada: str) -> None:
    # Los hostings dan "postgres://..."; SQLAlchemy necesita el driver psycopg explícito.
    assert normalize_database_url(entrada) == "postgresql+psycopg://u:p@host:5432/db"
