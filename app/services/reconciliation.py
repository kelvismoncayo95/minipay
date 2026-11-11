"""Conciliación: revisar que TODO el libro sume cero (si no, hay un bug)."""

import logging

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import LedgerEntry, ReconciliationRun

logger = logging.getLogger(__name__)


def run_reconciliation(db: Session) -> ReconciliationRun:
    """Suma todos los renglones, guarda el resultado y avisa en el log si no da cero."""
    total, cantidad = db.execute(
        select(func.coalesce(func.sum(LedgerEntry.amount), 0), func.count(LedgerEntry.id))
    ).one()
    run = ReconciliationRun(total=total, entries_count=cantidad, ok=(total == 0))
    db.add(run)
    db.flush()
    if not run.ok:
        logger.error("¡Libro descuadrado! Total = %s centavos", total)
    return run


def latest_run(db: Session) -> ReconciliationRun | None:
    return db.scalars(
        select(ReconciliationRun).order_by(ReconciliationRun.ran_at.desc()).limit(1)
    ).first()
