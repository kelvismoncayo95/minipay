"""Schemas de saldo y movimientos. Los montos siempre en centavos."""

import uuid
from datetime import datetime

from pydantic import BaseModel


class BalanceOut(BaseModel):
    account_id: uuid.UUID
    balance_cents: int


class SetBalanceRequest(BaseModel):
    balance_cents: int


class MovementOut(BaseModel):
    transaction_id: uuid.UUID
    kind: str
    amount_cents: int
    created_at: datetime
