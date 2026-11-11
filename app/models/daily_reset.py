"""Modelo de reinicios diarios: uno por día de demo (nunca dos)."""

import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class DailyReset(Base):
    __tablename__ = "daily_resets"

    # La fecha ES la clave primaria: imposible reiniciar dos veces el mismo día.
    day: Mapped[date] = mapped_column(Date, primary_key=True)
    transaction_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("ledger_transactions.id")
    )
    ran_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
