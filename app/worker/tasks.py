"""Tareas del worker. Cada tarea recibe `ctx` (contexto que le pasa Arq)."""

import asyncio
from typing import Any

from app.database import SessionLocal
from app.services.reconciliation import run_reconciliation


def _reconcile(session_factory: Any) -> dict[str, Any]:
    with session_factory() as db:
        run = run_reconciliation(db)
        db.commit()
        return {"ok": run.ok, "total": run.total, "entries": run.entries_count}


async def reconcile_ledger(ctx: dict[str, Any]) -> dict[str, Any]:
    """Conciliación del libro. El código de la base es sincrónico: va en un hilo aparte
    para no trabar el event loop de Arq."""
    factory = ctx.get("session_factory", SessionLocal)  # los tests pasan otra base
    return await asyncio.to_thread(_reconcile, factory)
