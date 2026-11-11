"""Modelo de claves de idempotencia: "este pedido ya lo procesé"."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class IdempotencyKey(Base):
    """Una clave enviada por un usuario y el movimiento que produjo."""

    __tablename__ = "idempotency_keys"
    __table_args__ = (
        # La clave es única POR USUARIO: Ana y Luis pueden usar la misma sin chocar.
        UniqueConstraint("user_id", "key", name="uq_idempotency_keys_user_key"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    key: Mapped[str] = mapped_column(Text)
    # Huella del pedido (destino + monto). Misma clave con otro pedido = error.
    request_hash: Mapped[str] = mapped_column(Text)
    transaction_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("ledger_transactions.id")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
