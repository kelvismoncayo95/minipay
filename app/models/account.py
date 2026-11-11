"""Modelo de la tabla accounts: cuentas de personas y del sistema."""

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Account(Base):
    """Una cuenta de dinero. El saldo no se guarda: se suma desde ledger_entries."""

    __tablename__ = "accounts"
    __table_args__ = (
        CheckConstraint(
            "kind IN ('user', 'system')",
            name="ck_accounts_kind",
        ),
        CheckConstraint(
            "(kind = 'system' AND user_id IS NULL)"
            " OR (kind = 'user' AND user_id IS NOT NULL)",
            name="ck_accounts_owner",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id"),
        unique=True,
    )
    kind: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
