"""Schemas de saldo y movimientos. Los montos siempre en centavos."""

import uuid
from datetime import datetime

from pydantic import BaseModel


class BalanceOut(BaseModel):
    account_id: uuid.UUID
    balance_cents: int


class SetBalanceRequest(BaseModel):
    balance_cents: int


class TransferRequest(BaseModel):
    to_username: str
    amount_cents: int


class TransferOut(BaseModel):
    transaction_id: uuid.UUID
    amount_cents: int
    balance_cents: int  # mi saldo después de transferir


class MovementOut(BaseModel):
    transaction_id: uuid.UUID
    kind: str
    amount_cents: int
    created_at: datetime
