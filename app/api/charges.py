"""Endpoints de cobros: el comercio cobra (/merchant/charges), la persona paga (/me/charges)."""

import uuid

from fastapi import APIRouter, Depends, Header, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.database import get_db
from app.models import User
from app.schemas.charges import ChargeOut, CreateChargeRequest
from app.services.charges import (
    ChargeAlreadyResolvedError,
    ChargeError,
    ChargeNotFoundError,
    create_charge,
    idempotent_pay,
    list_for_merchant,
    list_for_payer,
    reject_charge,
)
from app.services.idempotency import IdempotencyConflictError
from app.services.ledger import InsufficientFundsError, InvalidTransferError, LimitExceededError

merchant_router = APIRouter(prefix="/merchant", tags=["comercio"])
payer_router = APIRouter(prefix="/me", tags=["cobros"])

ERRORES = {
    ChargeNotFoundError: status.HTTP_404_NOT_FOUND,
    ChargeAlreadyResolvedError: status.HTTP_409_CONFLICT,
    ChargeError: status.HTTP_422_UNPROCESSABLE_ENTITY,
    InsufficientFundsError: status.HTTP_422_UNPROCESSABLE_ENTITY,
    LimitExceededError: status.HTTP_422_UNPROCESSABLE_ENTITY,
    InvalidTransferError: status.HTTP_422_UNPROCESSABLE_ENTITY,
    IdempotencyConflictError: status.HTTP_422_UNPROCESSABLE_ENTITY,
}


def to_http(error: Exception) -> HTTPException:
    return HTTPException(ERRORES[type(error)], str(error))


def require_merchant(user: User = Depends(get_current_user)) -> User:
    if user.role != "merchant":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Solo los comercios pueden cobrar.")
    return user


@merchant_router.post("/charges", response_model=ChargeOut, status_code=status.HTTP_201_CREATED)
def new_charge(
    body: CreateChargeRequest,
    merchant: User = Depends(require_merchant),
    db: Session = Depends(get_db),
) -> ChargeOut:
    try:
        charge = create_charge(
            db, merchant, body.payer_username, body.amount_cents, body.description
        )
    except ChargeError as error:
        raise to_http(error) from None
    db.commit()
    return ChargeOut.from_charge(charge)


@merchant_router.get("/charges", response_model=list[ChargeOut])
def merchant_charges(
    merchant: User = Depends(require_merchant), db: Session = Depends(get_db)
) -> list[ChargeOut]:
    return [ChargeOut.from_charge(c) for c in list_for_merchant(db, merchant.id)]


@payer_router.get("/charges", response_model=list[ChargeOut])
def my_charges(
    user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> list[ChargeOut]:
    """Cobros que me hicieron (pendientes y resueltos), el más nuevo primero."""
    return [ChargeOut.from_charge(c) for c in list_for_payer(db, user.id)]


@payer_router.post("/charges/{charge_id}/pay", response_model=ChargeOut)
def pay(
    charge_id: uuid.UUID,
    response: Response,
    idempotency_key: str = Header(alias="Idempotency-Key", min_length=8, max_length=100),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ChargeOut:
    try:
        charge, repetido = idempotent_pay(db, user.id, idempotency_key, charge_id)
    except tuple(ERRORES) as error:
        raise to_http(error) from None
    db.commit()
    if repetido:
        response.headers["Idempotent-Replayed"] = "true"
    return ChargeOut.from_charge(charge)


@payer_router.post("/charges/{charge_id}/reject", response_model=ChargeOut)
def reject(
    charge_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ChargeOut:
    try:
        charge = reject_charge(db, charge_id, user.id)
    except (ChargeNotFoundError, ChargeAlreadyResolvedError) as error:
        raise to_http(error) from None
    db.commit()
    return ChargeOut.from_charge(charge)
