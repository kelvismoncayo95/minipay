"""Información pública de la demo (para los textos del frontend)."""

from datetime import datetime

from fastapi import APIRouter
from pydantic import BaseModel

from app.core.demo import (
    CURRENCY,
    DAILY_TRANSFER_LIMIT,
    INITIAL_BALANCES,
    MAX_TRANSFER,
    RESET_HOUR,
    TIMEZONE,
    TOTAL_POOL,
)
from app.services.daily_reset import next_reset_at

router = APIRouter(prefix="/demo", tags=["demo"])


class DemoInfo(BaseModel):
    currency: str
    timezone: str
    reset_hour: int
    next_reset_at: datetime
    total_pool_cents: int
    initial_balances_cents: dict[str, int]
    max_transfer_cents: int
    daily_limit_cents: int


@router.get("/info", response_model=DemoInfo)
def info() -> DemoInfo:
    return DemoInfo(
        currency=CURRENCY,
        timezone=TIMEZONE,
        reset_hour=RESET_HOUR,
        next_reset_at=next_reset_at(),
        total_pool_cents=TOTAL_POOL,
        initial_balances_cents=INITIAL_BALANCES,
        max_transfer_cents=MAX_TRANSFER,
        daily_limit_cents=DAILY_TRANSFER_LIMIT,
    )
