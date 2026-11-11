"""Servicio de login: hash de contraseñas (bcrypt) y tokens de acceso (JWT)."""

import uuid
from datetime import UTC, datetime, timedelta

import bcrypt
import jwt
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import User

ALGORITHM = "HS256"


class InvalidTokenError(Exception):
    """El token está vencido, alterado o mal formado."""


def hash_password(password: str) -> str:
    """Convierte la contraseña en un hash con sal aleatoria. No se puede revertir."""
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, password_hash: str) -> bool:
    """¿Esta contraseña corresponde a este hash?"""
    return bcrypt.checkpw(password.encode(), password_hash.encode())


def authenticate(db: Session, username: str, password: str) -> User | None:
    """Devuelve el usuario si usuario y contraseña son correctos; si no, None."""
    user = db.scalars(select(User).where(User.username == username)).first()
    if user is None or user.password_hash is None:
        return None
    if not verify_password(password, user.password_hash):
        return None
    return user


def create_access_token(user_id: uuid.UUID, expires_in: timedelta | None = None) -> str:
    """Token firmado que dice "soy este usuario" y vence solo."""
    if expires_in is None:
        expires_in = timedelta(minutes=settings.jwt_expire_minutes)
    payload = {"sub": str(user_id), "exp": datetime.now(UTC) + expires_in}
    return jwt.encode(payload, settings.jwt_secret, algorithm=ALGORITHM)


def decode_access_token(token: str) -> uuid.UUID:
    """Verifica la firma y el vencimiento, y devuelve el id del usuario."""
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[ALGORITHM])
        return uuid.UUID(payload["sub"])
    except (jwt.PyJWTError, KeyError, ValueError) as error:
        raise InvalidTokenError("Token inválido o vencido.") from error
