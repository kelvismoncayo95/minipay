"""Modelo de cobros: un comercio le pide un pago a una persona."""

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.user import User


class Charge(Base):
    """Cobro: pending → paid (se movió el dinero) o rejected (la persona lo rechazó)."""

    __tablename__ = "charges"
    __table_args__ = (
        CheckConstraint("amount > 0", name="ck_charges_amount_positive"),
        CheckConstraint(
            "status IN ('pending', 'paid', 'rejected')",
            name="ck_charges_status",
        ),
        CheckConstraint(
            "(status = 'paid') = (transaction_id IS NOT NULL)",
            name="ck_charges_paid_has_transaction",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    merchant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    payer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    amount: Mapped[int] = mapped_column(BigInteger)
    description: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, server_default="pending")
    transaction_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("ledger_transactions.id")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    merchant: Mapped[User] = relationship(foreign_keys=[merchant_id])
    payer: Mapped[User] = relationship(foreign_keys=[payer_id])
