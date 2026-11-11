"""Tests del endpoint de conciliación del admin (paso 10)."""

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


def test_admin_corre_y_ve_la_conciliacion(client: TestClient) -> None:
    h = auth(client, "admin")
    client.put("/me/balance", json={"balance_cents": 1_000}, headers=auth(client, "ana"))

    r = client.post("/admin/reconciliation", headers=h)
    assert r.status_code == 200
    assert r.json()["ok"] is True
    assert r.json()["total_cents"] == 0
    assert client.get("/admin/reconciliation", headers=h).json()["ok"] is True


def test_una_persona_no_puede_ver_la_conciliacion(client: TestClient) -> None:
    assert client.get("/admin/reconciliation", headers=auth(client, "ana")).status_code == 403
