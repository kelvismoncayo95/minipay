"""El mismo cobro pagado dos veces AL MISMO TIEMPO (con claves distintas).

Ana tiene saldo de sobra, así que el saldo no frena nada: lo único que impide
pagar dos veces es bloquear la fila del cobro y revisar su estado.
"""

import threading
import uuid

import pytest
from sqlalchemy import Engine, delete, select
from sqlalchemy.orm import Session

from app.models import Account, Charge, LedgerEntry, LedgerTransaction, User
from app.services import ledger
from app.services.charges import ChargeAlreadyResolvedError, create_charge, pay_charge
from app.services.ledger import get_balance, set_balance


def test_cobro_pagado_dos_veces_a_la_vez(
    test_engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    sufijo = uuid.uuid4().hex[:8]
    extra: list[uuid.UUID] = []
    with Session(test_engine) as db:
        if db.scalars(select(Account).where(Account.kind == "system")).first() is None:
            banco = Account(kind="system")
            db.add(banco)
            db.flush()
            extra.append(banco.id)
        ana = User(username=f"ana-{sufijo}", display_name="Ana", role="user")
        clinica = User(username=f"clinica-{sufijo}", display_name="Clínica", role="merchant")
        db.add_all([ana, clinica])
        db.flush()
        c_ana, c_cli = Account(kind="user", user_id=ana.id), Account(kind="user", user_id=clinica.id)
        db.add_all([c_ana, c_cli])
        db.flush()
        set_balance(db, c_ana.id, 500_000)
        charge = create_charge(db, clinica, ana.username, 10_000, "Consulta")
        db.commit()
        ids = {"ana": ana.id, "clinica": clinica.id, "c_ana": c_ana.id, "c_cli": c_cli.id}
        charge_id = charge.id

    # Peor caso: después de leer el saldo, cada hilo espera al otro (máx. 1 s).
    despues_de_leer = threading.Barrier(2, timeout=1.0)

    def get_balance_lento(db: Session, account_id: uuid.UUID) -> int:
        saldo = get_balance(db, account_id)
        try:
            despues_de_leer.wait()
        except threading.BrokenBarrierError:
            pass
        return saldo

    monkeypatch.setattr(ledger, "get_balance", get_balance_lento)

    largada = threading.Barrier(2)
    resultados: list[str] = []

    def pagar() -> None:
        with Session(test_engine) as db:
            largada.wait()
            try:
                pay_charge(db, charge_id, ids["ana"])
                db.commit()
                resultados.append("pagado")
            except ChargeAlreadyResolvedError:
                db.rollback()
                resultados.append("ya pagado")

    hilos = [threading.Thread(target=pagar) for _ in range(2)]
    for t in hilos:
        t.start()
    for t in hilos:
        t.join()

    try:
        assert sorted(resultados) == ["pagado", "ya pagado"]
        with Session(test_engine) as db:
            assert get_balance(db, ids["c_ana"]) == 490_000
    finally:
        with Session(test_engine) as db:
            cuentas = [ids["c_ana"], ids["c_cli"]]
            tx = db.scalars(
                select(LedgerEntry.transaction_id).where(LedgerEntry.account_id.in_(cuentas))
            ).all()
            db.execute(delete(Charge).where(Charge.id == charge_id))
            db.execute(delete(LedgerEntry).where(LedgerEntry.transaction_id.in_(tx)))
            db.execute(delete(LedgerTransaction).where(LedgerTransaction.id.in_(tx)))
            db.execute(delete(Account).where(Account.id.in_(cuentas + extra)))
            db.execute(delete(User).where(User.id.in_([ids["ana"], ids["clinica"]])))
            db.commit()
