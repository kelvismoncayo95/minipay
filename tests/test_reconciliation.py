"""Tests de la conciliación y de la tarea del worker (paso 10)."""

import asyncio

from sqlalchemy import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.models import Account, LedgerEntry, LedgerTransaction, ReconciliationRun
from app.services.reconciliation import latest_run, run_reconciliation
from app.worker.tasks import reconcile_ledger


def test_libro_balanceado_da_ok(db: Session) -> None:
    banco, cuenta = Account(kind="system"), Account(kind="system")
    db.add_all([banco, cuenta])
    db.flush()
    tx = LedgerTransaction(kind="balance_set")
    tx.entries = [
        LedgerEntry(account_id=banco.id, amount=-500),
        LedgerEntry(account_id=cuenta.id, amount=500),
    ]
    db.add(tx)
    db.flush()

    run = run_reconciliation(db)
    assert (run.ok, run.total) == (True, 0)
    assert run.entries_count >= 2
    assert latest_run(db).id == run.id


def test_libro_descuadrado_se_detecta(db: Session) -> None:
    # Simulamos un bug: un renglón sin su pareja (dinero inventado).
    cuenta = Account(kind="system")
    tx = LedgerTransaction(kind="balance_set")
    db.add_all([cuenta, tx])
    db.flush()
    db.add(LedgerEntry(transaction_id=tx.id, account_id=cuenta.id, amount=777))
    db.flush()

    run = run_reconciliation(db)
    assert run.ok is False
    assert run.total == 777


def test_tarea_del_worker_guarda_una_corrida(test_engine: Engine) -> None:
    factory = sessionmaker(bind=test_engine)
    resultado = asyncio.run(reconcile_ledger({"session_factory": factory}))
    assert resultado["ok"] is True

    with factory() as db:  # limpieza: la tarea hizo commit de verdad
        db.query(ReconciliationRun).delete()
        db.commit()
