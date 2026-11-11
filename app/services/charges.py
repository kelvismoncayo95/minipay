"""Servicio de cobros: el comercio pide, la persona paga o rechaza. No hace commit."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Charge, LedgerTransaction, User
from app.services.idempotency import fingerprint, run_idempotent
from app.services.ledger import MAX_TRANSFER, get_account_for_user, move_money


class ChargeError(ValueError):
    """El cobro no es válido."""


class ChargeNotFoundError(LookupError):
    """No existe, o no es de este usuario (no se distingue: no se filtra información)."""


class ChargeAlreadyResolvedError(ValueError):
    """El cobro ya se pagó o se rechazó."""


def create_charge(
    db: Session, merchant: User, payer_username: str, amount: int, description: str
) -> Charge:
    if merchant.role != "merchant":
        raise ChargeError("Solo los comercios pueden cobrar.")
    if not 0 < amount <= MAX_TRANSFER:
        raise ChargeError(f"El monto tiene que estar entre 1 y {MAX_TRANSFER} centavos.")
    payer = db.scalars(
        select(User).where(User.username == payer_username, User.role == "user")
    ).first()
    if payer is None:
        raise ChargeError("No existe una persona con ese usuario.")

    charge = Charge(
        merchant_id=merchant.id, payer_id=payer.id, amount=amount, description=description
    )
    db.add(charge)
    db.flush()
    db.refresh(charge)  # trae status y created_at que pone la base
    return charge


def list_for_payer(db: Session, payer_id: uuid.UUID) -> list[Charge]:
    return list(
        db.scalars(
            select(Charge).where(Charge.payer_id == payer_id).order_by(Charge.created_at.desc())
        )
    )


def list_for_merchant(db: Session, merchant_id: uuid.UUID) -> list[Charge]:
    return list(
        db.scalars(
            select(Charge)
            .where(Charge.merchant_id == merchant_id)
            .order_by(Charge.created_at.desc())
        )
    )


def _lock_pending(db: Session, charge_id: uuid.UUID, payer_id: uuid.UUID) -> Charge:
    """Bloquea el cobro (FOR UPDATE) y verifica que siga pendiente."""
    charge = db.scalars(
        select(Charge)
        .where(Charge.id == charge_id, Charge.payer_id == payer_id)
        .with_for_update()
    ).first()
    if charge is None:
        raise ChargeNotFoundError("Cobro no encontrado.")
    if charge.status != "pending":
        raise ChargeAlreadyResolvedError(f"Este cobro ya está {charge.status}.")
    return charge


def pay_charge(db: Session, charge_id: uuid.UUID, payer_id: uuid.UUID) -> Charge:
    # Orden de bloqueo: primero el cobro, después las cuentas (dentro de move_money).
    charge = _lock_pending(db, charge_id, payer_id)
    origen = get_account_for_user(db, charge.payer_id)
    destino = get_account_for_user(db, charge.merchant_id)
    tx = move_money(db, origen.id, destino.id, charge.amount, kind="payment")
    charge.status = "paid"
    charge.transaction_id = tx.id
    charge.resolved_at = datetime.now(UTC)
    db.flush()
    return charge


def reject_charge(db: Session, charge_id: uuid.UUID, payer_id: uuid.UUID) -> Charge:
    charge = _lock_pending(db, charge_id, payer_id)
    charge.status = "rejected"
    charge.resolved_at = datetime.now(UTC)
    db.flush()
    return charge


def idempotent_pay(
    db: Session, payer_id: uuid.UUID, key: str, charge_id: uuid.UUID
) -> tuple[Charge, bool]:
    """Pago protegido contra pedidos repetidos (misma Idempotency-Key)."""

    def accion() -> LedgerTransaction:
        charge = pay_charge(db, charge_id, payer_id)
        return db.get(LedgerTransaction, charge.transaction_id)

    _, repetido = run_idempotent(db, payer_id, key, fingerprint("pay", charge_id), accion)
    return db.get(Charge, charge_id), repetido
