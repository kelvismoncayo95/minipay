"""Servicio del libro contable: saldos, transferencias y límites.

Estas funciones NO hacen commit: quien las llama (el endpoint) decide cuándo guardar.
Así varias operaciones pueden ir juntas en una sola transacción.
"""

import uuid
from datetime import timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.demo import (
    DAILY_PAYMENT_LIMIT,
    DAILY_TRANSFER_LIMIT,
    LIMITS_BY_KIND,
    MAX_PAYMENT,
    MAX_TRANSFER,
)
from app.models import Account, LedgerEntry, LedgerTransaction, User

# Se reexportan (ver app/core/demo.py).
__all__ = ["DAILY_PAYMENT_LIMIT", "DAILY_TRANSFER_LIMIT", "MAX_PAYMENT", "MAX_TRANSFER"]

# set_balance ya no lo usa la demo pública (ahora hay un fondo fijo). Queda como
# herramienta interna para tests y para cargar datos.
BALANCE_MIN = 100  # US$1
BALANCE_MAX = 500_000  # US$5.000
BALANCE_CHANGES_PER_HOUR = 5


def dinero(cents: int) -> str:
    """Centavos → texto para personas: 50000 → "US$500", 4550 → "US$45,50"."""
    enteros = f"{abs(cents) // 100:,}".replace(",", ".")
    resto = abs(cents) % 100
    signo = "-" if cents < 0 else ""
    return f"{signo}US${enteros}" + (f",{resto:02d}" if resto else "")


def last_reset_seq(db: Session) -> int:
    """`seq` del último reinicio diario (0 si nunca hubo). Marca el inicio del "día de demo"."""
    return db.scalar(
        select(func.coalesce(func.max(LedgerTransaction.seq), 0)).where(
            LedgerTransaction.kind == "daily_reset"
        )
    )


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


def _sent_today(db: Session, account_id: uuid.UUID, kind: str) -> int:
    """Centavos que salieron en el día de demo (desde el último reinicio) con ese tipo de movimiento."""
    enviado = db.scalar(
        select(func.coalesce(func.sum(LedgerEntry.amount), 0))
        .join(LedgerEntry.transaction)
        .where(
            LedgerEntry.account_id == account_id,
            LedgerEntry.amount < 0,
            LedgerTransaction.kind == kind,
            LedgerTransaction.seq > last_reset_seq(db),
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


def list_entries(
    db: Session, account_id: uuid.UUID, limit: int = 50, since_seq: int = 0
) -> list[LedgerEntry]:
    """Renglones de una cuenta (desde el movimiento `since_seq`), del más nuevo al más viejo."""
    consulta = (
        select(LedgerEntry)
        .join(LedgerEntry.transaction)
        .where(LedgerEntry.account_id == account_id, LedgerTransaction.seq >= since_seq)
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
            f"El saldo tiene que estar entre {dinero(BALANCE_MIN)} y {dinero(BALANCE_MAX)}."
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
        raise LimitExceededError(f"El máximo por operación es {dinero(MAX_TRANSFER)}.")

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
    maximo, maximo_dia = LIMITS_BY_KIND[kind]
    que = "transferido" if kind == "transfer" else "pagado"
    if amount <= 0:
        raise InvalidTransferError("El monto tiene que ser mayor que cero.")
    if amount > maximo:
        raise LimitExceededError(f"El máximo por operación es {dinero(maximo)}.")

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
    # Cada tipo tiene su propio límite diario: transferir no le quita margen a pagar.
    if _sent_today(db, origen.id, kind) + amount > maximo_dia:
        raise LimitExceededError(f"Superás el límite diario de {dinero(maximo_dia)} {que}s.")
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
