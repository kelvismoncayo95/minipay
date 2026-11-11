"""Endpoints de login: /auth/login y /auth/me."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.database import get_db
from app.models import User
from app.schemas.auth import LoginRequest, TokenResponse, UserOut
from app.services.auth import authenticate, create_access_token

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    """Usuario + contraseña → token de acceso."""
    user = authenticate(db, body.username, body.password)
    if user is None:
        # Mismo mensaje para usuario o contraseña mal: no se revela cuál falló.
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario o contraseña incorrectos.",
        )
    return TokenResponse(access_token=create_access_token(user.id))


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)) -> User:
    """Quién soy (según el token)."""
    return user
