"""Modelos de minipay. Se importan acá para que Alembic encuentre todas las tablas."""

from app.models.account import Account
from app.models.user import User

__all__ = ["Account", "User"]
