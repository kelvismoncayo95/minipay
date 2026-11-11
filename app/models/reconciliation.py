"""Modelo de conciliaciones: cada revisión de "todo el libro suma cero"."""

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ReconciliationRun(Base):
    __tablename__ = "reconciliation_runs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    total: Mapped[int] = mapped_column(BigInteger)  # suma de TODOS los renglones
    entries_count: Mapped[int] = mapped_column(BigInteger)
    ok: Mapped[bool]  # total == 0
    ran_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
