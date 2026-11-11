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
            created_at=c.created_at,
            resolved_at=c.resolved_at,
        )
