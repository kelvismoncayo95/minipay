"""Endpoints de la cuenta del usuario logueado: saldo, transferencias y movimientos.

Desde el modelo de fondo fijo (2026-11-11) ya no se "elige saldo": cada persona arranca
el día con su saldo inicial y el dinero circula entre las cuentas.
"""

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.database import get_db
from app.models import Account, User
from app.schemas.accounts import BalanceOut, MovementOut, TransferOut, TransferRequest
from app.services.idempotency import IdempotencyConflictError, idempotent_transfer
from app.services.ledger import (
    InsufficientFundsError,
    InvalidTransferError,
    LimitExceededError,
    get_account_for_user,
    get_balance,
    last_reset_seq,
    list_entries,
)

router = APIRouter(prefix="/me", tags=["cuenta"])


def get_my_account(
    user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> Account:
    """La cuenta del usuario logueado; 404 si no tiene (el admin)."""
    account = get_account_for_user(db, user.id)
    if account is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Este usuario no tiene cuenta de dinero.")
    return account


@router.get("/balance", response_model=BalanceOut)
def read_balance(
    account: Account = Depends(get_my_account), db: Session = Depends(get_db)
) -> BalanceOut:
    return BalanceOut(account_id=account.id, balance_cents=get_balance(db, account.id))


@router.post("/transfers", response_model=TransferOut, status_code=status.HTTP_201_CREATED)
def make_transfer(
    body: TransferRequest,
    response: Response,
    idempotency_key: str = Header(alias="Idempotency-Key", min_length=8, max_length=100),
    user: User = Depends(get_current_user),
    account: Account = Depends(get_my_account),
    db: Session = Depends(get_db),
) -> TransferOut:
    """Mandarle dinero a otra persona.

    Requiere el header `Idempotency-Key` (ej. un UUID nuevo por cada transferencia).
    Si el mismo pedido llega dos veces con la misma clave, se cobra una sola vez.
    """
    if user.role != "user":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Solo las personas pueden transferir.")
    try:
        tx, repetido = idempotent_transfer(
            db, user.id, account.id, idempotency_key, body.to_username, body.amount_cents
        )
    except (
        InvalidTransferError,
        InsufficientFundsError,
        LimitExceededError,
        IdempotencyConflictError,
    ) as error:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(error)) from None
    db.commit()
    if repetido:
        response.headers["Idempotent-Replayed"] = "true"
    return TransferOut(
        transaction_id=tx.id,
        amount_cents=body.amount_cents,
        balance_cents=get_balance(db, account.id),
    )


@router.get("/movements", response_model=list[MovementOut])
def read_movements(
    all_history: bool = Query(False, alias="all", description="true = también días anteriores"),
    account: Account = Depends(get_my_account),
    db: Session = Depends(get_db),
) -> list[MovementOut]:
    """Movimientos de mi cuenta del día de demo (desde el último reinicio), el más nuevo primero.

    El historial completo sigue en la base: `?all=true` lo devuelve.
    """
    desde = 0 if all_history else last_reset_seq(db)
    return [
        MovementOut(
            transaction_id=e.transaction_id,
            kind=e.transaction.kind,
            amount_cents=e.amount,
            created_at=e.transaction.created_at,
        )
        for e in list_entries(db, account.id, since_seq=desde)
    ]
