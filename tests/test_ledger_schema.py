"""Tests del esquema del libro: las reglas de la base rechazan datos inválidos."""

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Account, LedgerEntry, LedgerTransaction, User


def crear_usuario(db: Session, username: str = "ana") -> User:
    user = User(username=username, display_name="Ana", role="user")
    db.add(user)
    db.flush()
    return user


def test_role_invalido_rechazado(db: Session) -> None:
    db.add(User(username="ana", display_name="Ana", role="jefe"))
    with pytest.raises(IntegrityError, match="ck_users_role"):
        db.flush()


def test_username_repetido_rechazado(db: Session) -> None:
    crear_usuario(db, "ana")
    db.add(User(username="ana", display_name="Otra Ana", role="user"))
    with pytest.raises(IntegrityError, match="users_username_key"):
        db.flush()


def test_cuenta_del_sistema_con_dueno_rechazada(db: Session) -> None:
    ana = crear_usuario(db)
    db.add(Account(kind="system", user_id=ana.id))
    with pytest.raises(IntegrityError, match="ck_accounts_owner"):
        db.flush()


def test_cuenta_de_persona_sin_dueno_rechazada(db: Session) -> None:
    db.add(Account(kind="user", user_id=None))
    with pytest.raises(IntegrityError, match="ck_accounts_owner"):
        db.flush()


def test_renglon_en_cero_rechazado(db: Session) -> None:
    banco = Account(kind="system")
    tx = LedgerTransaction(kind="balance_set")
    db.add_all([banco, tx])
    db.flush()
    db.add(LedgerEntry(transaction_id=tx.id, account_id=banco.id, amount=0))
    with pytest.raises(IntegrityError, match="ck_ledger_entries_amount_not_zero"):
        db.flush()


def test_cambio_de_saldo_suma_cero(db: Session) -> None:
    """Ana elige $1.000: Banco -100000, Ana +100000. Todo suma cero."""
    ana = crear_usuario(db)
    banco = Account(kind="system")
    cuenta_ana = Account(kind="user", user_id=ana.id)
    db.add_all([banco, cuenta_ana])
    db.flush()

    tx = LedgerTransaction(kind="balance_set")
    tx.entries = [
        LedgerEntry(account_id=banco.id, amount=-100_000),
        LedgerEntry(account_id=cuenta_ana.id, amount=100_000),
    ]
    db.add(tx)
    db.flush()

    def saldo(account_id) -> int:
        consulta = select(func.coalesce(func.sum(LedgerEntry.amount), 0)).where(
            LedgerEntry.account_id == account_id
        )
        return db.scalar(consulta)

    assert saldo(cuenta_ana.id) == 100_000
    assert saldo(banco.id) == -100_000
    assert db.scalar(select(func.sum(LedgerEntry.amount))) == 0
