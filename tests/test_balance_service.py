"""Tests del servicio de saldo: calcular y elegir saldo (paso 3)."""

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Account, LedgerEntry, User
from app.services.ledger import (
    BALANCE_MAX,
    BALANCE_MIN,
    InvalidBalanceError,
    get_balance,
    set_balance,
)


@pytest.fixture
def banco(db: Session) -> Account:
    cuenta = Account(kind="system")
    db.add(cuenta)
    db.flush()
    return cuenta


@pytest.fixture
def cuenta_ana(db: Session) -> Account:
    ana = User(username="ana", display_name="Ana", role="user")
    db.add(ana)
    db.flush()
    cuenta = Account(kind="user", user_id=ana.id)
    db.add(cuenta)
    db.flush()
    return cuenta


def suma_total(db: Session) -> int:
    return db.scalar(select(func.coalesce(func.sum(LedgerEntry.amount), 0)))


def test_limites_son_los_de_la_demo() -> None:
    assert BALANCE_MIN == 100  # $1
    assert BALANCE_MAX == 500_000  # $5.000


def test_saldo_de_cuenta_nueva_es_cero(db: Session, cuenta_ana: Account) -> None:
    assert get_balance(db, cuenta_ana.id) == 0


def test_elegir_saldo_crea_movimiento_que_suma_cero(
    db: Session, banco: Account, cuenta_ana: Account
) -> None:
    tx = set_balance(db, cuenta_ana.id, 100_000)

    assert tx is not None
    assert tx.kind == "balance_set"
    assert sorted(e.amount for e in tx.entries) == [-100_000, 100_000]
    assert get_balance(db, cuenta_ana.id) == 100_000
    assert get_balance(db, banco.id) == -100_000
    assert suma_total(db) == 0


def test_cambiar_saldo_mueve_solo_la_diferencia(
    db: Session, banco: Account, cuenta_ana: Account
) -> None:
    set_balance(db, cuenta_ana.id, 100_000)
    tx = set_balance(db, cuenta_ana.id, 30_000)

    montos = {e.account_id: e.amount for e in tx.entries}
    assert montos == {cuenta_ana.id: -70_000, banco.id: 70_000}
    assert get_balance(db, cuenta_ana.id) == 30_000
    assert suma_total(db) == 0


def test_elegir_el_mismo_saldo_no_crea_movimiento(
    db: Session, banco: Account, cuenta_ana: Account
) -> None:
    set_balance(db, cuenta_ana.id, 50_000)
    assert set_balance(db, cuenta_ana.id, 50_000) is None
    assert get_balance(db, cuenta_ana.id) == 50_000


@pytest.mark.parametrize("monto", [100, 500_000])
def test_limites_exactos_permitidos(
    db: Session, banco: Account, cuenta_ana: Account, monto: int
) -> None:
    set_balance(db, cuenta_ana.id, monto)
    assert get_balance(db, cuenta_ana.id) == monto


@pytest.mark.parametrize("monto", [-100, 0, 99, 500_001])
def test_saldo_fuera_de_rango_rechazado(
    db: Session, banco: Account, cuenta_ana: Account, monto: int
) -> None:
    with pytest.raises(InvalidBalanceError):
        set_balance(db, cuenta_ana.id, monto)
    assert get_balance(db, cuenta_ana.id) == 0


def test_cuenta_del_sistema_no_puede_elegir_saldo(db: Session, banco: Account) -> None:
    with pytest.raises(InvalidBalanceError):
        set_balance(db, banco.id, 10_000)
