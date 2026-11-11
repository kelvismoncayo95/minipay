"""Fixtures compartidas: una sesión de base de datos que se deshace al terminar cada test."""

from collections.abc import Generator

import pytest
from sqlalchemy.orm import Session

from app.database import engine


@pytest.fixture
def db() -> Generator[Session, None, None]:
    """Abre una transacción, entrega la sesión al test y al final la deshace (rollback).

    Así cada test empieza con la base limpia y no deja basura.
    """
    connection = engine.connect()
    outer = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    try:
        yield session
    finally:
        session.close()
        outer.rollback()
        connection.close()
