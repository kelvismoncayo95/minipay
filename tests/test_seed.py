"""Tests de los datos demo (paso 3)."""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Account, User
from app.seed import seed_demo


def test_seed_crea_usuarios_demo_y_banco(db: Session) -> None:
    seed_demo(db)

    usuarios = {u.username: u.role for u in db.scalars(select(User))}
    assert usuarios == {
        "ana": "user",
        "luis": "user",
        "marta": "user",
        "pedro": "user",
        "clinica-del-sur": "merchant",
        "admin": "admin",
    }
    assert db.scalar(select(func.count()).where(Account.kind == "system")) == 1
    # Personas y comercio tienen cuenta; el admin no maneja dinero.
    assert db.scalar(select(func.count()).where(Account.kind == "user")) == 5


def test_seed_es_idempotente(db: Session) -> None:
    seed_demo(db)
    seed_demo(db)

    assert db.scalar(select(func.count()).select_from(User)) == 6
    assert db.scalar(select(func.count()).select_from(Account)) == 6
