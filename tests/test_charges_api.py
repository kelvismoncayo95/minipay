"""Tests de los endpoints de cobros (paso 9)."""

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


@pytest.fixture
def h(client: TestClient) -> dict[str, dict[str, str]]:
    hs = {u: auth(client, u) for u in ("ana", "luis", "clinica-del-sur")}
    return hs


def cobrar(client: TestClient, h: dict, monto: int = 30_000) -> dict:
    r = client.post(
        "/merchant/charges",
        json={"payer_username": "ana", "amount_cents": monto, "description": "Consulta"},
        headers=h["clinica-del-sur"],
    )
    assert r.status_code == 201
    return r.json()


def pagar(client: TestClient, headers: dict, charge_id: str, key: str | None = None):
    return client.post(
        f"/me/charges/{charge_id}/pay",
        headers={**headers, "Idempotency-Key": key or str(uuid.uuid4())},
    )


def test_flujo_completo(client: TestClient, h: dict) -> None:
    charge = cobrar(client, h)
    assert charge["status"] == "pending"
    assert charge["merchant_username"] == "clinica-del-sur"

    pendientes = client.get("/me/charges", headers=h["ana"]).json()
    assert [c["id"] for c in pendientes] == [charge["id"]]

    r = pagar(client, h["ana"], charge["id"])
    assert r.status_code == 200
    assert r.json()["status"] == "paid"
    assert client.get("/me/balance", headers=h["ana"]).json()["balance_cents"] == 220_000
    assert (
        client.get("/me/balance", headers=h["clinica-del-sur"]).json()["balance_cents"] == 30_000
    )
    del_comercio = client.get("/merchant/charges", headers=h["clinica-del-sur"]).json()
    assert del_comercio[0]["status"] == "paid"


def test_reintento_del_pago_con_la_misma_clave(client: TestClient, h: dict) -> None:
    charge = cobrar(client, h)
    r1 = pagar(client, h["ana"], charge["id"], key="pago-consulta-1")
    r2 = pagar(client, h["ana"], charge["id"], key="pago-consulta-1")
    assert r1.status_code == r2.status_code == 200
    assert r2.headers["Idempotent-Replayed"] == "true"
    assert client.get("/me/balance", headers=h["ana"]).json()["balance_cents"] == 220_000


def test_pagar_dos_veces_con_otra_clave_da_409(client: TestClient, h: dict) -> None:
    charge = cobrar(client, h)
    pagar(client, h["ana"], charge["id"])
    assert pagar(client, h["ana"], charge["id"]).status_code == 409


def test_rechazar(client: TestClient, h: dict) -> None:
    charge = cobrar(client, h)
    r = client.post(f"/me/charges/{charge['id']}/reject", headers=h["ana"])
    assert r.status_code == 200
    assert r.json()["status"] == "rejected"


def test_otro_usuario_no_ve_el_cobro(client: TestClient, h: dict) -> None:
    charge = cobrar(client, h)
    assert pagar(client, h["luis"], charge["id"]).status_code == 404
    assert client.get("/me/charges", headers=h["luis"]).json() == []


def test_una_persona_no_puede_cobrar(client: TestClient, h: dict) -> None:
    r = client.post(
        "/merchant/charges",
        json={"payer_username": "luis", "amount_cents": 1_000, "description": "x"},
        headers=h["ana"],
    )
    assert r.status_code == 403


def test_cobro_mayor_al_maximo_rechazado(client: TestClient, h: dict) -> None:
    r = client.post(
        "/merchant/charges",
        json={"payer_username": "ana", "amount_cents": 100_001, "description": "Cirugía"},
        headers=h["clinica-del-sur"],
    )
    assert r.status_code == 422


def test_cobro_de_1000_permitido(client: TestClient, h: dict) -> None:
    charge = cobrar(client, h, monto=100_000)  # US$1.000: el máximo por cobro
    assert pagar(client, h["ana"], charge["id"]).status_code == 200


def test_transferir_no_impide_pagar_un_cobro(client: TestClient, h: dict) -> None:
    # Límites separados: Ana llena su límite de transferencias...
    for _ in range(2):
        client.post(
            "/me/transfers",
            json={"to_username": "luis", "amount_cents": 50_000},
            headers={**h["ana"], "Idempotency-Key": str(uuid.uuid4())},
        )
    # ...y todavía puede pagarle a la Clínica.
    charge = cobrar(client, h, monto=1_000)
    assert pagar(client, h["ana"], charge["id"]).status_code == 200


def test_limite_diario_de_pagos(client: TestClient, h: dict) -> None:
    for _ in range(2):  # US$2.000 pagados: justo el límite
        charge = cobrar(client, h, monto=100_000)
        assert pagar(client, h["ana"], charge["id"]).status_code == 200
    charge = cobrar(client, h, monto=100)
    r = pagar(client, h["ana"], charge["id"])
    assert r.status_code == 422
    assert "límite diario" in r.json()["detail"]
