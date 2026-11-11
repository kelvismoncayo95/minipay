"""Servicio del libro contable: calcular y elegir saldo.

Estas funciones NO hacen commit: quien las llama (el endpoint) decide cuándo guardar.
Así varias operaciones pueden ir juntas en una sola transacción.
"""

import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Account, LedgerEntry, LedgerTransaction

# Límites de la demo, en centavos (ver ESTADO 2.1).
BALANCE_MIN = 100  # $1
BALANCE_MAX = 500_000  # $5.000


class InvalidBalanceError(ValueError):
    """El saldo pedido no está permitido."""


def get_balance(db: Session, account_id: uuid.UUID) -> int:
    """Saldo de una cuenta = suma de todos sus renglones (0 si no tiene)."""
    consulta = select(func.coalesce(func.sum(LedgerEntry.amount), 0)).where(
        LedgerEntry.account_id == account_id
    )
    return db.scalar(consulta)


def get_account_for_user(db: Session, user_id: uuid.UUID) -> Account | None:
    """La cuenta de dinero de un usuario (None si no tiene, ej. el admin)."""
    return db.scalars(select(Account).where(Account.user_id == user_id)).first()


def list_entries(db: Session, account_id: uuid.UUID, limit: int = 50) -> list[LedgerEntry]:
    """Renglones de una cuenta, del más nuevo al más viejo."""
    consulta = (
        select(LedgerEntry)
        .join(LedgerEntry.transaction)
        .where(LedgerEntry.account_id == account_id)
        .order_by(LedgerTransaction.seq.desc())
        .limit(limit)
    )
    return list(db.scalars(consulta))


def get_system_account(db: Session) -> Account:
    """La cuenta del Banco de juguete. Tiene que existir exactamente una."""
    return db.scalars(select(Account).where(Account.kind == "system")).one()


def set_balance(
    db: Session, account_id: uuid.UUID, new_balance: int
) -> LedgerTransaction | None:
    """Deja la cuenta con `new_balance` centavos moviendo la diferencia con el Banco.

    Devuelve el movimiento creado, o None si el saldo ya era ese.
    """
    if not BALANCE_MIN <= new_balance <= BALANCE_MAX:
        raise InvalidBalanceError(
            f"El saldo tiene que estar entre {BALANCE_MIN} y {BALANCE_MAX} centavos."
        )

    # FOR UPDATE: bloquea la fila de la cuenta hasta el commit.
    # Si llegan dos pedidos a la vez, el segundo espera al primero.
    cuenta = db.scalars(
        select(Account).where(Account.id == account_id).with_for_update()
    ).one_or_none()
    if cuenta is None or cuenta.kind != "user":
        raise InvalidBalanceError("Solo las cuentas de personas pueden elegir saldo.")

    diferencia = new_balance - get_balance(db, cuenta.id)
    if diferencia == 0:
        return None

    banco = get_system_account(db)
    tx = LedgerTransaction(kind="balance_set")
    tx.entries = [
        LedgerEntry(account_id=banco.id, amount=-diferencia),
        LedgerEntry(account_id=cuenta.id, amount=diferencia),
    ]
    db.add(tx)
    db.flush()
    return tx
