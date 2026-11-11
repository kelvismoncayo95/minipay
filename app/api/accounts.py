"""Endpoints de la cuenta del usuario logueado: /me/balance y /me/movements."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.database import get_db
from app.models import Account, User
from app.schemas.accounts import (
    BalanceOut,
    MovementOut,
    SetBalanceRequest,
    TransferOut,
    TransferRequest,
)
from app.services.ledger import (
    InsufficientFundsError,
    InvalidBalanceError,
    InvalidTransferError,
    get_account_for_user,
    get_balance,
    list_entries,
    set_balance,
    transfer,
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


@router.put("/balance", response_model=BalanceOut)
def choose_balance(
    body: SetBalanceRequest,
    user: User = Depends(get_current_user),
    account: Account = Depends(get_my_account),
    db: Session = Depends(get_db),
) -> BalanceOut:
    """Elegir el saldo de juguete. Solo personas (el comercio cobra, no elige)."""
    if user.role != "user":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Solo las personas pueden elegir saldo.")
    try:
        set_balance(db, account.id, body.balance_cents)
    except InvalidBalanceError as error:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(error)) from None
    db.commit()
    return BalanceOut(account_id=account.id, balance_cents=get_balance(db, account.id))


@router.post("/transfers", response_model=TransferOut, status_code=status.HTTP_201_CREATED)
def make_transfer(
    body: TransferRequest,
    user: User = Depends(get_current_user),
    account: Account = Depends(get_my_account),
    db: Session = Depends(get_db),
) -> TransferOut:
    """Mandarle dinero a otra persona."""
    if user.role != "user":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Solo las personas pueden transferir.")
    try:
        tx = transfer(db, account.id, body.to_username, body.amount_cents)
    except (InvalidTransferError, InsufficientFundsError) as error:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(error)) from None
    db.commit()
    return TransferOut(
        transaction_id=tx.id,
        amount_cents=body.amount_cents,
        balance_cents=get_balance(db, account.id),
    )


@router.get("/movements", response_model=list[MovementOut])
def read_movements(
    account: Account = Depends(get_my_account), db: Session = Depends(get_db)
) -> list[MovementOut]:
    """Últimos 50 movimientos de mi cuenta, el más nuevo primero."""
    return [
        MovementOut(
            transaction_id=e.transaction_id,
            kind=e.transaction.kind,
            amount_cents=e.amount,
            created_at=e.transaction.created_at,
        )
        for e in list_entries(db, account.id)
    ]
