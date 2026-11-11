"""Modelo de la tabla users: las personas y el comercio de la demo."""

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class User(Base):
    """Una persona, comercio o administrador de minipay."""

    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint(
            "role IN ('user', 'merchant', 'admin')",
            name="ck_users_role",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    username: Mapped[str] = mapped_column(Text, unique=True)
    display_name: Mapped[str] = mapped_column(Text)
    role: Mapped[str] = mapped_column(Text)
    # Nunca la contraseña: solo su hash (bcrypt). Vacío = no puede entrar.
    password_hash: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
