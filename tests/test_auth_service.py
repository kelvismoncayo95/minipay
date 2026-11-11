"""Tests del servicio de login: hash de contraseñas y tokens (paso 4)."""

import uuid
from datetime import timedelta

import pytest
from sqlalchemy.orm import Session

from app.models import User
from app.services.auth import (
    InvalidTokenError,
    authenticate,
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)


def test_el_hash_no_es_la_contrasena() -> None:
    h = hash_password("demo1234")
    assert h != "demo1234"
    assert h.startswith("$2b$")  # formato bcrypt


def test_mismo_password_da_hashes_distintos() -> None:
    # Por la "sal" aleatoria: dos usuarios con la misma contraseña no se delatan.
    assert hash_password("demo1234") != hash_password("demo1234")


def test_verificar_contrasena() -> None:
    h = hash_password("demo1234")
    assert verify_password("demo1234", h) is True
    assert verify_password("otra", h) is False


def test_authenticate(db: Session) -> None:
    ana = User(
        username="ana", display_name="Ana", role="user", password_hash=hash_password("demo1234")
    )
    sin_clave = User(username="luis", display_name="Luis", role="user")
    db.add_all([ana, sin_clave])
    db.flush()

    assert authenticate(db, "ana", "demo1234") == ana
    assert authenticate(db, "ana", "mal") is None
    assert authenticate(db, "nadie", "demo1234") is None
    assert authenticate(db, "luis", "demo1234") is None  # sin hash no entra


def test_token_ida_y_vuelta() -> None:
    user_id = uuid.uuid4()
    token = create_access_token(user_id)
    assert decode_access_token(token) == user_id


def test_token_vencido_rechazado() -> None:
    token = create_access_token(uuid.uuid4(), expires_in=timedelta(seconds=-1))
    with pytest.raises(InvalidTokenError):
        decode_access_token(token)


def test_token_alterado_rechazado() -> None:
    token = create_access_token(uuid.uuid4())
    with pytest.raises(InvalidTokenError):
        decode_access_token(token[:-2] + "xx")
