"""Tests de reembolsos: el comercio devuelve el total de un cobro pagado (paso 12)."""

import uuid
from collections.abc import Generator
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.main import app
from app.models import LedgerEntry
from app.seed import DEMO_PASSWORD, seed_demo
from app.services.daily_reset import ensure_daily_reset


@pytest.fixture
def client(db: Session) -> Generator[TestClient, None, None]:
    seed_demo(db)
    app.dependency_overrides[get_db] = lambda: db
    yield TestClient(app)
    app.dependency_overrides.clear()


def auth(client: TestClient, username: str) -> dict[str, str]:
    r = client.post("/auth/login", json={"username": username, "password": DEMO_PASSWORD})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def key() -> dict[str, str]:
    return {"Idempotency-Key": str(uuid.uuid4())}


@pytest.fixture
def h(client: TestClient) -> dict:
    return {u: auth(client, u) for u in ("ana", "luis", "clinica-del-sur")}


def cobro_pagado(client: TestClient, h: dict, monto: int = 30_000) -> dict:
    charge = client.post(
        "/merchant/charges",
        json={"payer_username": "ana", "amount_cents": monto, "description": "Consulta"},
        headers=h["clinica-del-sur"],
    ).json()
    r = client.post(f"/me/charges/{charge['id']}/pay", headers={**h["ana"], **key()})
    assert r.status_code == 200
    return r.json()


def saldo(client: TestClient, headers: dict) -> int:
    return client.get("/me/balance", headers=headers).json()["balance_cents"]


def reembolsar(client: TestClient, h: dict, charge_id: str, k: dict | None = None):
    return client.post(
        f"/merchant/charges/{charge_id}/refund", headers={**h["clinica-del-sur"], **(k or key())}
    )


def test_reembolso_devuelve_el_dinero(client: TestClient, h: dict, db: Session) -> None:
    charge = cobro_pagado(client, h)
    assert saldo(client, h["ana"]) == 220_000

    r = reembolsar(client, h, charge["id"])
    assert r.status_code == 200
    assert r.json()["status"] == "refunded"
    assert r.json()["refund_transaction_id"]
    assert saldo(client, h["ana"]) == 250_000
    assert saldo(client, h["clinica-del-sur"]) == 0
    assert db.scalar(select(func.sum(LedgerEntry.amount))) == 0

    mov = client.get("/me/movements", headers=h["ana"]).json()[0]
    assert (mov["kind"], mov["amount_cents"]) == ("refund", 30_000)


def test_no_se_reembolsa_dos_veces(client: TestClient, h: dict) -> None:
    charge = cobro_pagado(client, h)
    reembolsar(client, h, charge["id"])
    assert reembolsar(client, h, charge["id"]).status_code == 409
    assert saldo(client, h["ana"]) == 250_000


def test_reintento_con_la_misma_clave(client: TestClient, h: dict) -> None:
    charge = cobro_pagado(client, h)
    k = key()
    r1, r2 = reembolsar(client, h, charge["id"], k), reembolsar(client, h, charge["id"], k)
    assert r1.status_code == r2.status_code == 200
    assert r2.headers["Idempotent-Replayed"] == "true"


def test_solo_se_reembolsan_cobros_pagados(client: TestClient, h: dict) -> None:
    pendiente = client.post(
        "/merchant/charges",
        json={"payer_username": "ana", "amount_cents": 1_000, "description": "x"},
        headers=h["clinica-del-sur"],
    ).json()
    assert reembolsar(client, h, pendiente["id"]).status_code == 409


def test_una_persona_no_puede_reembolsar(client: TestClient, h: dict) -> None:
    charge = cobro_pagado(client, h)
    r = client.post(f"/merchant/charges/{charge['id']}/refund", headers={**h["ana"], **key()})
    assert r.status_code == 403


def test_cobro_inexistente_da_404(client: TestClient, h: dict) -> None:
    assert reembolsar(client, h, str(uuid.uuid4())).status_code == 404


def test_sin_saldo_el_comercio_no_puede_reembolsar(client: TestClient, h: dict, db: Session) -> None:
    charge = cobro_pagado(client, h)
    # Al día siguiente la Clínica vuelve a US$0: ya no tiene con qué devolver.
    ensure_daily_reset(db, now=datetime(2099, 1, 1, 12, tzinfo=UTC))
    r = reembolsar(client, h, charge["id"])
    assert r.status_code == 422
    assert "Saldo insuficiente" in r.json()["detail"]


def test_comprobante_del_reembolso(client: TestClient, h: dict) -> None:
    charge = cobro_pagado(client, h)
    refund_tx = reembolsar(client, h, charge["id"]).json()["refund_transaction_id"]
    r = client.get(f"/me/receipts/{refund_tx}", headers=h["ana"])
    assert r.status_code == 200
    assert "minipay-REE-" in r.headers["content-disposition"]
