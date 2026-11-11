"""Tests de los endpoints de login (paso 4)."""

from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.database import get_db
from app.main import app
from app.seed import DEMO_PASSWORD, seed_demo


@pytest.fixture
def client(db: Session) -> Generator[TestClient, None, None]:
    """Cliente HTTP de prueba que usa la sesión de tests en vez de la base real."""
    seed_demo(db)
    app.dependency_overrides[get_db] = lambda: db
    yield TestClient(app)
    app.dependency_overrides.clear()


def login(client: TestClient, username: str, password: str):
    return client.post("/auth/login", json={"username": username, "password": password})


def test_contrasena_demo_es_simple() -> None:
    assert DEMO_PASSWORD == "demo1234"


def test_login_correcto_devuelve_token(client: TestClient) -> None:
    r = login(client, "ana", DEMO_PASSWORD)
    assert r.status_code == 200
    body = r.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]


@pytest.mark.parametrize(("username", "password"), [("ana", "mal"), ("nadie", "demo1234")])
def test_login_incorrecto_mismo_mensaje(client: TestClient, username: str, password: str) -> None:
    # Mismo mensaje si falla el usuario o la contraseña: no se le dice al atacante cuál acertó.
    r = login(client, username, password)
    assert r.status_code == 401
    assert r.json()["detail"] == "Usuario o contraseña incorrectos."


def test_me_con_token(client: TestClient) -> None:
    token = login(client, "clinica-del-sur", DEMO_PASSWORD).json()["access_token"]
    r = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.json()["username"] == "clinica-del-sur"
    assert r.json()["role"] == "merchant"
    assert "password_hash" not in r.json()


def test_me_sin_token_rechazado(client: TestClient) -> None:
    assert client.get("/auth/me").status_code == 401


def test_me_con_token_falso_rechazado(client: TestClient) -> None:
    r = client.get("/auth/me", headers={"Authorization": "Bearer inventado"})
    assert r.status_code == 401
