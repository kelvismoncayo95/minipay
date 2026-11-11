"""Servicio del libro contable: calcular y elegir saldo.

Estas funciones NO hacen commit: quien las llama (el endpoint) decide cuándo guardar.
Así varias operaciones pueden ir juntas en una sola transacción.
"""

import uuid
from datetime import timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Account, LedgerEntry, LedgerTransaction, User

# Límites de la demo, en centavos (ver ESTADO 2.1).
BALANCE_MIN = 100  # $1
BALANCE_MAX = 500_000  # $5.000
MAX_TRANSFER = 500_000  # $5.000 por operación
DAILY_TRANSFER_LIMIT = 1_000_000  # $10.000 enviados por día (día UTC)
BALANCE_CHANGES_PER_HOUR = 5


class InvalidBalanceError(ValueError):
    """El saldo pedido no está permitido."""


class InvalidTransferError(ValueError):
    """La transferencia no es válida (monto, destinatario...)."""


class InsufficientFundsError(ValueError):
    """La cuenta no tiene saldo suficiente."""


class LimitExceededError(ValueError):
    """La operación supera un límite de monto (por operación o diario)."""


class RateLimitError(ValueError):
    """Demasiadas operaciones en poco tiempo."""


def _count_balance_changes_last_hour(db: Session, account_id: uuid.UUID) -> int:
    return db.scalar(
        select(func.count())
        .select_from(LedgerEntry)
        .join(LedgerEntry.transaction)
        .where(
            LedgerEntry.account_id == account_id,
            LedgerTransaction.kind == "balance_set",
            LedgerTransaction.created_at > func.now() - timedelta(hours=1),
        )
    )


def _sent_today(db: Session, account_id: uuid.UUID) -> int:
    """Centavos enviados hoy (día UTC) por transferencias y pagos."""
    enviado = db.scalar(
        select(func.coalesce(func.sum(LedgerEntry.amount), 0))
        .join(LedgerEntry.transaction)
        .where(
            LedgerEntry.account_id == account_id,
            LedgerEntry.amount < 0,
            LedgerTransaction.kind.in_(["transfer", "payment"]),
            LedgerTransaction.created_at >= func.date_trunc("day", func.now()),
        )
    )
    return -enviado


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
    if _count_balance_changes_last_hour(db, cuenta.id) >= BALANCE_CHANGES_PER_HOUR:
        raise RateLimitError(
            f"Máximo {BALANCE_CHANGES_PER_HOUR} cambios de saldo por hora. Probá más tarde."
        )

    banco = get_system_account(db)
    tx = LedgerTransaction(kind="balance_set")
    tx.entries = [
        LedgerEntry(account_id=banco.id, amount=-diferencia),
        LedgerEntry(account_id=cuenta.id, amount=diferencia),
    ]
    db.add(tx)
    db.flush()
    return tx


def transfer(
    db: Session, from_account_id: uuid.UUID, to_username: str, amount: int
) -> LedgerTransaction:
    """Pasa `amount` centavos de una cuenta a la de otra persona. No hace commit."""
    if amount <= 0:
        raise InvalidTransferError("El monto tiene que ser mayor que cero.")
    if amount > MAX_TRANSFER:
        raise LimitExceededError(f"El máximo por operación es {MAX_TRANSFER} centavos.")

    destino = db.scalars(
        select(Account)
        .join(User, Account.user_id == User.id)
        .where(User.username == to_username, User.role == "user")
    ).first()
    if destino is None:
        raise InvalidTransferError("No existe una persona con ese usuario.")
    if destino.id == from_account_id:
        raise InvalidTransferError("No podés transferirte a vos mismo.")
    return move_money(db, from_account_id, destino.id, amount, kind="transfer")


def move_money(
    db: Session, from_account_id: uuid.UUID, to_account_id: uuid.UUID, amount: int, kind: str
) -> LedgerTransaction:
    """Mueve dinero entre dos cuentas de usuario con todas las reglas. No hace commit.

    La usan las transferencias y los pagos de cobros.
    """
    if amount <= 0:
        raise InvalidTransferError("El monto tiene que ser mayor que cero.")
    if amount > MAX_TRANSFER:
        raise LimitExceededError(f"El máximo por operación es {MAX_TRANSFER} centavos.")

    # Bloqueamos las DOS cuentas, siempre en el mismo orden (por id).
    # Si dos operaciones cruzadas (A→B y B→A) bloquearan en distinto orden,
    # cada una esperaría a la otra para siempre (deadlock).
    bloqueadas = db.scalars(
        select(Account)
        .where(Account.id.in_([from_account_id, to_account_id]))
        .order_by(Account.id)
        .with_for_update()
    ).all()
    origen = next((a for a in bloqueadas if a.id == from_account_id), None)
    if origen is None or origen.kind != "user":
        raise InvalidTransferError("La cuenta de origen no puede enviar dinero.")

    # Con la fila bloqueada, saldo y total del día ya no pueden cambiar hasta el commit.
    if _sent_today(db, origen.id) + amount > DAILY_TRANSFER_LIMIT:
        raise LimitExceededError(
            f"Superás el límite diario de {DAILY_TRANSFER_LIMIT} centavos enviados."
        )
    if get_balance(db, origen.id) < amount:
        raise InsufficientFundsError("Saldo insuficiente.")

    tx = LedgerTransaction(kind=kind)
    tx.entries = [
        LedgerEntry(account_id=origen.id, amount=-amount),
        LedgerEntry(account_id=to_account_id, amount=amount),
    ]
    db.add(tx)
    db.flush()
    return tx
