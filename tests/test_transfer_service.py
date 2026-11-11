"""Tests del servicio de transferencias (paso 6)."""

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Account, LedgerEntry, User
from app.services.ledger import (
    InsufficientFundsError,
    InvalidTransferError,
    get_balance,
    set_balance,
    transfer,
)


def crear_cuenta(db: Session, username: str, role: str = "user") -> Account:
    user = User(username=username, display_name=username.title(), role=role)
    db.add(user)
    db.flush()
    cuenta = Account(kind="user", user_id=user.id)
    db.add(cuenta)
    db.flush()
    return cuenta


@pytest.fixture
def cuentas(db: Session) -> dict[str, Account]:
    db.add(Account(kind="system"))
    db.flush()
    c = {
        "ana": crear_cuenta(db, "ana"),
        "luis": crear_cuenta(db, "luis"),
        "clinica": crear_cuenta(db, "clinica-del-sur", role="merchant"),
    }
    set_balance(db, c["ana"].id, 100_000)  # Ana arranca con $1.000
    return c


def test_transferencia_mueve_el_dinero(db: Session, cuentas: dict[str, Account]) -> None:
    tx = transfer(db, cuentas["ana"].id, "luis", 25_000)

    assert tx.kind == "transfer"
    assert {e.account_id: e.amount for e in tx.entries} == {
        cuentas["ana"].id: -25_000,
        cuentas["luis"].id: 25_000,
    }
    assert get_balance(db, cuentas["ana"].id) == 75_000
    assert get_balance(db, cuentas["luis"].id) == 25_000
    assert db.scalar(select(func.sum(LedgerEntry.amount))) == 0


def test_se_puede_transferir_todo_el_saldo(db: Session, cuentas: dict[str, Account]) -> None:
    transfer(db, cuentas["ana"].id, "luis", 100_000)
    assert get_balance(db, cuentas["ana"].id) == 0


def test_saldo_insuficiente(db: Session, cuentas: dict[str, Account]) -> None:
    with pytest.raises(InsufficientFundsError):
        transfer(db, cuentas["ana"].id, "luis", 100_001)
    assert get_balance(db, cuentas["ana"].id) == 100_000


@pytest.mark.parametrize("monto", [0, -500])
def test_monto_debe_ser_positivo(db: Session, cuentas: dict[str, Account], monto: int) -> None:
    with pytest.raises(InvalidTransferError):
        transfer(db, cuentas["ana"].id, "luis", monto)


def test_no_a_uno_mismo(db: Session, cuentas: dict[str, Account]) -> None:
    with pytest.raises(InvalidTransferError):
        transfer(db, cuentas["ana"].id, "ana", 1_000)


def test_destinatario_inexistente(db: Session, cuentas: dict[str, Account]) -> None:
    with pytest.raises(InvalidTransferError):
        transfer(db, cuentas["ana"].id, "nadie", 1_000)


def test_no_a_un_comercio(db: Session, cuentas: dict[str, Account]) -> None:
    # Pagarle a un comercio es un "cobro" (paso 9), no una transferencia.
    with pytest.raises(InvalidTransferError):
        transfer(db, cuentas["ana"].id, "clinica-del-sur", 1_000)
