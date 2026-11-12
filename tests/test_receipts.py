"""Tests del comprobante en PDF (paso 11)."""

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


def transferir(client: TestClient, h: dict, a: str, monto: int) -> str:
    r = client.post(
        "/me/transfers",
        json={"to_username": a, "amount_cents": monto},
        headers={**h, "Idempotency-Key": str(uuid.uuid4())},
    )
    return r.json()["transaction_id"]


def test_comprobante_de_transferencia_en_pdf(client: TestClient) -> None:
    ana = auth(client, "ana")
    tx = transferir(client, ana, "luis", 4_550)

    r = client.get(f"/me/receipts/{tx}", headers=ana)
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
    assert r.content.startswith(b"%PDF")
    assert f"minipay-TRF-{tx[:8].upper()}.pdf" in r.headers["content-disposition"]


def test_el_que_recibe_tambien_puede_bajarlo(client: TestClient) -> None:
    tx = transferir(client, auth(client, "ana"), "luis", 1_000)
    assert client.get(f"/me/receipts/{tx}", headers=auth(client, "luis")).status_code == 200


def test_un_tercero_no_puede_bajarlo(client: TestClient) -> None:
    tx = transferir(client, auth(client, "ana"), "luis", 1_000)
    assert client.get(f"/me/receipts/{tx}", headers=auth(client, "marta")).status_code == 404


def test_comprobante_de_pago_de_cobro(client: TestClient) -> None:
    clinica, ana = auth(client, "clinica-del-sur"), auth(client, "ana")
    charge = client.post(
        "/merchant/charges",
        json={"payer_username": "ana", "amount_cents": 2_000, "description": "Consulta"},
        headers=clinica,
    ).json()
    pagado = client.post(
        f"/me/charges/{charge['id']}/pay", headers={**ana, "Idempotency-Key": str(uuid.uuid4())}
    ).json()
    assert pagado["transaction_id"]  # el cobro pagado expone su movimiento
    r = client.get(f"/me/receipts/{pagado['transaction_id']}", headers=clinica)
    assert r.status_code == 200
    assert "minipay-PAG-" in r.headers["content-disposition"]


def test_no_hay_comprobante_de_un_reinicio(client: TestClient) -> None:
    ana = auth(client, "ana")
    reinicio = client.get("/me/movements", headers=ana).json()[-1]
    assert reinicio["kind"] == "daily_reset"
    assert client.get(f"/me/receipts/{reinicio['transaction_id']}", headers=ana).status_code == 404


def test_sin_token(client: TestClient) -> None:
    assert client.get(f"/me/receipts/{uuid.uuid4()}").status_code == 401
