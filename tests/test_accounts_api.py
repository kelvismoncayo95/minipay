"""Tests de la API de saldo y movimientos (paso 5)."""

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


def test_saldo_inicial_es_cero(client: TestClient) -> None:
    r = client.get("/me/balance", headers=auth(client, "ana"))
    assert r.status_code == 200
    assert r.json()["balance_cents"] == 0


def test_elegir_saldo(client: TestClient) -> None:
    h = auth(client, "ana")
    r = client.put("/me/balance", json={"balance_cents": 100_000}, headers=h)
    assert r.status_code == 200
    assert r.json()["balance_cents"] == 100_000
    assert client.get("/me/balance", headers=h).json()["balance_cents"] == 100_000


def test_elegir_saldo_fuera_de_rango(client: TestClient) -> None:
    r = client.put("/me/balance", json={"balance_cents": 50}, headers=auth(client, "ana"))
    assert r.status_code == 422
    assert "entre" in r.json()["detail"]


def test_movimientos_mas_nuevo_primero(client: TestClient) -> None:
    h = auth(client, "ana")
    client.put("/me/balance", json={"balance_cents": 100_000}, headers=h)
    client.put("/me/balance", json={"balance_cents": 30_000}, headers=h)

    r = client.get("/me/movements", headers=h)
    assert r.status_code == 200
    movimientos = r.json()
    assert [m["amount_cents"] for m in movimientos] == [-70_000, 100_000]
    assert all(m["kind"] == "balance_set" for m in movimientos)


def test_saldo_de_un_usuario_no_se_ve_en_otro(client: TestClient) -> None:
    client.put("/me/balance", json={"balance_cents": 100_000}, headers=auth(client, "ana"))
    r = client.get("/me/balance", headers=auth(client, "luis"))
    assert r.json()["balance_cents"] == 0


def test_admin_no_tiene_cuenta(client: TestClient) -> None:
    r = client.get("/me/balance", headers=auth(client, "admin"))
    assert r.status_code == 404


def test_comercio_no_elige_saldo(client: TestClient) -> None:
    r = client.put(
        "/me/balance", json={"balance_cents": 10_000}, headers=auth(client, "clinica-del-sur")
    )
    assert r.status_code == 403


def test_sin_token_rechazado(client: TestClient) -> None:
    assert client.get("/me/balance").status_code == 401
    assert client.get("/me/movements").status_code == 401


def test_sexto_cambio_de_saldo_en_una_hora_da_429(client: TestClient) -> None:
    h = auth(client, "ana")
    for monto in (100, 200, 300, 400, 500):
        assert client.put("/me/balance", json={"balance_cents": monto}, headers=h).status_code == 200
    r = client.put("/me/balance", json={"balance_cents": 600}, headers=h)
    assert r.status_code == 429
