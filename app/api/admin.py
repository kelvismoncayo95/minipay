"""Endpoints del administrador: conciliación del libro."""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.database import get_db
from app.models import ReconciliationRun, User
from app.services.reconciliation import latest_run, run_reconciliation

router = APIRouter(prefix="/admin", tags=["admin"])


class ReconciliationOut(BaseModel):
    ok: bool
    total_cents: int
    entries_count: int
    ran_at: datetime

    @classmethod
    def from_run(cls, r: ReconciliationRun) -> "ReconciliationOut":
        return cls(ok=r.ok, total_cents=r.total, entries_count=r.entries_count, ran_at=r.ran_at)


def require_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != "admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Solo el administrador.")
    return user


@router.get("/reconciliation", response_model=ReconciliationOut)
def last_reconciliation(
    _: User = Depends(require_admin), db: Session = Depends(get_db)
) -> ReconciliationOut:
    """Última conciliación (la corre el worker cada 15 minutos)."""
    run = latest_run(db)
    if run is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Todavía no hay conciliaciones.")
    return ReconciliationOut.from_run(run)


@router.post("/reconciliation", response_model=ReconciliationOut)
def reconcile_now(
    _: User = Depends(require_admin), db: Session = Depends(get_db)
) -> ReconciliationOut:
    """Correr una conciliación ahora mismo."""
    run = run_reconciliation(db)
    db.commit()
    db.refresh(run)
    return ReconciliationOut.from_run(run)
