"""Fixtures compartidas.

Los tests usan una base SEPARADA (`<nombre>_test`), nunca la de desarrollo.
Cada test corre dentro de una transacción que se deshace al terminar.
"""

from collections.abc import Generator

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.core.config import settings


@pytest.fixture(scope="session")
def test_engine() -> Generator[Engine, None, None]:
    """Crea la base de tests si no existe y le aplica todas las migraciones."""
    url = make_url(settings.database_url)
    test_url = url.set(database=f"{url.database}_test")

    admin = create_engine(url, isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        existe = conn.scalar(
            text("SELECT 1 FROM pg_database WHERE datname = :nombre"),
            {"nombre": test_url.database},
        )
        if not existe:
            conn.execute(text(f'CREATE DATABASE "{test_url.database}"'))
    admin.dispose()

    config = Config("alembic.ini")
    config.attributes["database_url"] = test_url
    command.upgrade(config, "head")

    engine = create_engine(test_url)
    yield engine
    engine.dispose()


@pytest.fixture
def db(test_engine: Engine) -> Generator[Session, None, None]:
    """Abre una transacción, entrega la sesión al test y al final la deshace (rollback)."""
    connection = test_engine.connect()
    outer = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    try:
        yield session
    finally:
        session.close()
        outer.rollback()
        connection.close()
