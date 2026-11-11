"""Dependencias compartidas de los endpoints."""

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.services.auth import InvalidTokenError, decode_access_token
from app.services.daily_reset import ensure_daily_reset

bearer = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: Session = Depends(get_db),
) -> User:
    """Lee el token del header `Authorization: Bearer ...` y devuelve el usuario."""
    no_autorizado = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Hay que iniciar sesión.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if credentials is None:
        raise no_autorizado
    try:
        user_id = decode_access_token(credentials.credentials)
    except InvalidTokenError:
        raise no_autorizado from None

    user = db.get(User, user_id)
    if user is None:
        raise no_autorizado

    # Si pasaron las 3:00 (Uruguay) y nadie reinició todavía, se reinicia ahora.
    # Así funciona aunque el servidor haya estado dormido a esa hora (Render gratis).
    if ensure_daily_reset(db):
        db.commit()
    return user
