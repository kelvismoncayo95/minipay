"""Tests de idempotencia: el mismo pedido dos veces se procesa una sola vez (paso 7)."""

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Account, LedgerTransaction, User
from app.services.idempotency import IdempotencyConflictError, idempotent_transfer
from app.services.ledger import InsufficientFundsError, get_balance, set_balance


def crear(db: Session, username: str) -> tuple[User, Account]:
    user = User(username=username, display_name=username.title(), role="user")
    db.add(user)
    db.flush()
    cuenta = Account(kind="user", user_id=user.id)
    db.add(cuenta)
    db.flush()
    return user, cuenta


@pytest.fixture
def gente(db: Session) -> dict:
    db.add(Account(kind="system"))
    db.flush()
    ana, cuenta_ana = crear(db, "ana")
    luis, cuenta_luis = crear(db, "luis")
    set_balance(db, cuenta_ana.id, 100_000)
    set_balance(db, cuenta_luis.id, 100_000)
    return {"ana": ana, "cuenta_ana": cuenta_ana, "luis": luis, "cuenta_luis": cuenta_luis}


def transferencias(db: Session) -> int:
    return db.scalar(select(func.count()).where(LedgerTransaction.kind == "transfer"))


def test_misma_clave_dos_veces_se_procesa_una(db: Session, gente: dict) -> None:
    tx1, repetido1 = idempotent_transfer(
        db, gente["ana"].id, gente["cuenta_ana"].id, "clave-0001", "luis", 10_000
    )
    tx2, repetido2 = idempotent_transfer(
        db, gente["ana"].id, gente["cuenta_ana"].id, "clave-0001", "luis", 10_000
    )

    assert (repetido1, repetido2) == (False, True)
    assert tx1.id == tx2.id
    assert transferencias(db) == 1
    assert get_balance(db, gente["cuenta_ana"].id) == 90_000  # se cobró UNA vez


def test_claves_distintas_son_pedidos_distintos(db: Session, gente: dict) -> None:
    idempotent_transfer(db, gente["ana"].id, gente["cuenta_ana"].id, "clave-0001", "luis", 10_000)
    idempotent_transfer(db, gente["ana"].id, gente["cuenta_ana"].id, "clave-0002", "luis", 10_000)
    assert transferencias(db) == 2


def test_misma_clave_con_otro_pedido_es_error(db: Session, gente: dict) -> None:
    idempotent_transfer(db, gente["ana"].id, gente["cuenta_ana"].id, "clave-0001", "luis", 10_000)
    with pytest.raises(IdempotencyConflictError):
        idempotent_transfer(
            db, gente["ana"].id, gente["cuenta_ana"].id, "clave-0001", "luis", 99_000
        )
    assert transferencias(db) == 1


def test_la_clave_es_por_usuario(db: Session, gente: dict) -> None:
    idempotent_transfer(db, gente["ana"].id, gente["cuenta_ana"].id, "clave-0001", "luis", 10_000)
    _, repetido = idempotent_transfer(
        db, gente["luis"].id, gente["cuenta_luis"].id, "clave-0001", "ana", 10_000
    )
    assert repetido is False
    assert transferencias(db) == 2


def test_si_falla_la_clave_no_queda_usada(db: Session, gente: dict) -> None:
    set_balance(db, gente["cuenta_ana"].id, 30_000)  # Ana tiene US$300
    with pytest.raises(InsufficientFundsError):
        idempotent_transfer(
            db, gente["ana"].id, gente["cuenta_ana"].id, "clave-0001", "luis", 40_000
        )
    # Ana recibe más saldo y reintenta con la MISMA clave: ahora sí sale.
    set_balance(db, gente["cuenta_ana"].id, 40_000)
    _, repetido = idempotent_transfer(
        db, gente["ana"].id, gente["cuenta_ana"].id, "clave-0001", "luis", 40_000
    )
    assert repetido is False
    assert get_balance(db, gente["cuenta_ana"].id) == 0
