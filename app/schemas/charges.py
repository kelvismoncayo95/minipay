"""Schemas de cobros."""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.models import Charge


class CreateChargeRequest(BaseModel):
    payer_username: str
    amount_cents: int
    description: str = Field(min_length=1, max_length=200)


class ChargeOut(BaseModel):
    id: uuid.UUID
    merchant_username: str
    payer_username: str
    amount_cents: int
    description: str
    status: str
    transaction_id: uuid.UUID | None  # el movimiento del pago (para el comprobante)
    refund_transaction_id: uuid.UUID | None
    refunded_at: datetime | None
    created_at: datetime
    resolved_at: datetime | None

    @classmethod
    def from_charge(cls, c: Charge) -> "ChargeOut":
        return cls(
            id=c.id,
            merchant_username=c.merchant.username,
            payer_username=c.payer.username,
            amount_cents=c.amount,
            description=c.description,
            status=c.status,
            transaction_id=c.transaction_id,
            refund_transaction_id=c.refund_transaction_id,
            refunded_at=c.refunded_at,
            created_at=c.created_at,
            resolved_at=c.resolved_at,
        )
