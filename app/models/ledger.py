"""Modelos del libro contable: movimientos (tickets) y sus renglones. Solo se agregan."""

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, Identity, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class LedgerTransaction(Base):
    """Un movimiento de dinero. Sus renglones siempre suman cero."""

    __tablename__ = "ledger_transactions"
    __table_args__ = (
        CheckConstraint(
            "kind IN ('balance_set', 'transfer', 'payment', 'daily_reset')",
            name="ck_ledger_transactions_kind",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    # Número de orden que pone la base (1, 2, 3…). Es interno: nunca se muestra en la API.
    # Sirve para ordenar sin empates: dos movimientos pueden tener el mismo created_at.
    seq: Mapped[int] = mapped_column(BigInteger, Identity(), unique=True)
    kind: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    entries: Mapped[list["LedgerEntry"]] = relationship(back_populates="transaction")


class LedgerEntry(Base):
    """Un renglón: cuánto entra (+) o sale (-) de una cuenta, en centavos."""

    __tablename__ = "ledger_entries"
    __table_args__ = (
        CheckConstraint("amount <> 0", name="ck_ledger_entries_amount_not_zero"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    transaction_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("ledger_transactions.id"),
    )
    account_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("accounts.id"),
        index=True,
    )
    amount: Mapped[int] = mapped_column(BigInteger)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    transaction: Mapped[LedgerTransaction] = relationship(back_populates="entries")
