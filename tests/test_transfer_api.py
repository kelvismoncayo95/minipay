"""Tests del endpoint de transferencias (paso 6)."""

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


@pytest.fixture
def ana(client: TestClient) -> dict[str, str]:
    h = auth(client, "ana")
    client.put("/me/balance", json={"balance_cents": 100_000}, headers=h)
    return h


def mandar(client: TestClient, h: dict[str, str], to: str, monto: int):
    return client.post("/me/transfers", json={"to_username": to, "amount_cents": monto}, headers=h)


def test_transferir(client: TestClient, ana: dict[str, str]) -> None:
    r = mandar(client, ana, "luis", 25_000)
    assert r.status_code == 201
    assert r.json()["amount_cents"] == 25_000
    assert r.json()["balance_cents"] == 75_000

    luis = auth(client, "luis")
    assert client.get("/me/balance", headers=luis).json()["balance_cents"] == 25_000
    mov = client.get("/me/movements", headers=luis).json()[0]
    assert (mov["kind"], mov["amount_cents"]) == ("transfer", 25_000)


def test_saldo_insuficiente(client: TestClient, ana: dict[str, str]) -> None:
    r = mandar(client, ana, "luis", 200_000)
    assert r.status_code == 422
    assert "Saldo insuficiente" in r.json()["detail"]


def test_destinatario_inexistente(client: TestClient, ana: dict[str, str]) -> None:
    assert mandar(client, ana, "nadie", 1_000).status_code == 422


def test_comercio_no_transfiere(client: TestClient) -> None:
    r = mandar(client, auth(client, "clinica-del-sur"), "luis", 1_000)
    assert r.status_code == 403


def test_sin_token(client: TestClient) -> None:
    assert client.post("/me/transfers", json={"to_username": "luis", "amount_cents": 1}).status_code == 401
