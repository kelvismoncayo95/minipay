"""Tests de la API de saldo y movimientos (fondo fijo, desde 2026-11-11)."""

import uuid
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.database import get_db
from app.main import app
from app.seed import DEMO_PASSWORD, seed_demo


@pytest.fixture
def client(db: Session) -> Generator[TestClient, None, None]:
    seed_demo(db)
    app.dependency_overrides[get_db] = lambda: db
    yield TestClient(app)
    app.dependency_overrides.clear()


def auth(client: TestClient, username: str) -> dict[str, str]:
    r = client.post("/auth/login", json={"username": username, "password": DEMO_PASSWORD})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_cada_persona_arranca_el_dia_con_2500(client: TestClient) -> None:
    r = client.get("/me/balance", headers=auth(client, "ana"))
    assert r.status_code == 200
    assert r.json()["balance_cents"] == 250_000


def test_el_comercio_arranca_en_cero(client: TestClient) -> None:
    r = client.get("/me/balance", headers=auth(client, "clinica-del-sur"))
    assert r.json()["balance_cents"] == 0


def test_ya_no_se_puede_elegir_saldo(client: TestClient) -> None:
    r = client.put("/me/balance", json={"balance_cents": 100}, headers=auth(client, "ana"))
    assert r.status_code == 405  # el endpoint ya no existe para PUT


def test_movimientos_del_dia(client: TestClient) -> None:
    h = auth(client, "ana")
    client.post(
        "/me/transfers",
        json={"to_username": "luis", "amount_cents": 1_000},
        headers={**h, "Idempotency-Key": str(uuid.uuid4())},
    )
    movs = client.get("/me/movements", headers=h).json()
    assert [(m["kind"], m["amount_cents"]) for m in movs] == [
        ("transfer", -1_000),
        ("daily_reset", 250_000),  # el "saldo inicial del día"
    ]


def test_saldo_de_un_usuario_no_se_ve_en_otro(client: TestClient) -> None:
    h = auth(client, "ana")
    client.post(
        "/me/transfers",
        json={"to_username": "marta", "amount_cents": 1_000},
        headers={**h, "Idempotency-Key": str(uuid.uuid4())},
    )
    assert client.get("/me/balance", headers=auth(client, "luis")).json()["balance_cents"] == 250_000


def test_admin_no_tiene_cuenta(client: TestClient) -> None:
    assert client.get("/me/balance", headers=auth(client, "admin")).status_code == 404


def test_sin_token_rechazado(client: TestClient) -> None:
    assert client.get("/me/balance").status_code == 401
    assert client.get("/me/movements").status_code == 401


def test_info_de_la_demo(client: TestClient) -> None:
    info = client.get("/demo/info").json()
    assert info["currency"] == "USD"
    assert info["timezone"] == "America/Montevideo"
    assert info["total_pool_cents"] == 1_000_000  # US$10.000
    assert info["max_transfer_cents"] == 50_000
    assert info["daily_limit_cents"] == 100_000
