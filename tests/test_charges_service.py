"""Tests del servicio de cobros (paso 9)."""

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Account, LedgerEntry, User
from app.services.charges import (
    ChargeAlreadyResolvedError,
    ChargeError,
    ChargeNotFoundError,
    create_charge,
    pay_charge,
    reject_charge,
)
from app.services.ledger import InsufficientFundsError, get_balance, set_balance


def crear(db: Session, username: str, role: str = "user") -> tuple[User, Account]:
    user = User(username=username, display_name=username.title(), role=role)
    db.add(user)
    db.flush()
    cuenta = Account(kind="user", user_id=user.id)
    db.add(cuenta)
    db.flush()
    return user, cuenta


@pytest.fixture
def g(db: Session) -> dict:
    db.add(Account(kind="system"))
    db.flush()
    ana, c_ana = crear(db, "ana")
    luis, _ = crear(db, "luis")
    clinica, c_clinica = crear(db, "clinica-del-sur", role="merchant")
    set_balance(db, c_ana.id, 100_000)
    return {"ana": ana, "c_ana": c_ana, "luis": luis, "clinica": clinica, "c_clinica": c_clinica}


def test_crear_cobro_queda_pendiente_y_no_mueve_dinero(db: Session, g: dict) -> None:
    charge = create_charge(db, g["clinica"], "ana", 30_000, "Consulta")
    assert charge.status == "pending"
    assert get_balance(db, g["c_ana"].id) == 100_000


def test_pagar_cobro_mueve_el_dinero(db: Session, g: dict) -> None:
    charge = create_charge(db, g["clinica"], "ana", 30_000, "Consulta")
    pagado = pay_charge(db, charge.id, g["ana"].id)

    assert pagado.status == "paid"
    assert pagado.transaction_id is not None
    assert get_balance(db, g["c_ana"].id) == 70_000
    assert get_balance(db, g["c_clinica"].id) == 30_000
    assert db.scalar(select(func.sum(LedgerEntry.amount))) == 0


def test_no_se_paga_dos_veces(db: Session, g: dict) -> None:
    charge = create_charge(db, g["clinica"], "ana", 30_000, "Consulta")
    pay_charge(db, charge.id, g["ana"].id)
    with pytest.raises(ChargeAlreadyResolvedError):
        pay_charge(db, charge.id, g["ana"].id)
    assert get_balance(db, g["c_ana"].id) == 70_000


def test_rechazar_cobro(db: Session, g: dict) -> None:
    charge = create_charge(db, g["clinica"], "ana", 30_000, "Consulta")
    assert reject_charge(db, charge.id, g["ana"].id).status == "rejected"
    with pytest.raises(ChargeAlreadyResolvedError):
        pay_charge(db, charge.id, g["ana"].id)


def test_solo_el_pagador_ve_y_paga_su_cobro(db: Session, g: dict) -> None:
    charge = create_charge(db, g["clinica"], "ana", 30_000, "Consulta")
    with pytest.raises(ChargeNotFoundError):
        pay_charge(db, charge.id, g["luis"].id)


def test_pagar_sin_saldo_deja_el_cobro_pendiente(db: Session, g: dict) -> None:
    charge = create_charge(db, g["clinica"], "ana", 200_000, "Cirugía")
    with pytest.raises(InsufficientFundsError):
        pay_charge(db, charge.id, g["ana"].id)
    db.refresh(charge)
    assert charge.status == "pending"


def test_solo_comercios_cobran(db: Session, g: dict) -> None:
    with pytest.raises(ChargeError):
        create_charge(db, g["luis"], "ana", 1_000, "No soy comercio")


@pytest.mark.parametrize("monto", [0, -1, 500_001])
def test_monto_invalido(db: Session, g: dict, monto: int) -> None:
    with pytest.raises(ChargeError):
        create_charge(db, g["clinica"], "ana", monto, "x")


def test_solo_se_cobra_a_personas(db: Session, g: dict) -> None:
    with pytest.raises(ChargeError):
        create_charge(db, g["clinica"], "clinica-del-sur", 1_000, "A mí mismo")
    with pytest.raises(ChargeError):
        create_charge(db, g["clinica"], "nadie", 1_000, "No existe")
