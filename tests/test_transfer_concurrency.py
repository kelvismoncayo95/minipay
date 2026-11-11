"""Test de concurrencia: dos transferencias AL MISMO TIEMPO desde la misma cuenta.

Ana tiene $100 y manda $80 a Luis y $80 a Marta a la vez.
Solo una puede salir bien. Si salen las dos, Ana queda en -$60: dinero inventado.

Este test NO usa la fixture `db` (rollback), porque necesita commits reales
en conexiones separadas. Limpia lo que crea al final.
"""

import threading
import uuid

import pytest
from sqlalchemy import Engine, delete, select
from sqlalchemy.orm import Session

from app.models import Account, LedgerEntry, LedgerTransaction, User
from app.services import ledger
from app.services.ledger import InsufficientFundsError, get_balance, set_balance, transfer


def test_dos_transferencias_simultaneas_no_dejan_saldo_negativo(
    test_engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    sufijo = uuid.uuid4().hex[:8]
    nombres = {k: f"{k}-{sufijo}" for k in ("ana", "luis", "marta")}

    with Session(test_engine) as db:
        creados: list[uuid.UUID] = []  # cuentas a borrar al final
        banco = db.scalars(select(Account).where(Account.kind == "system")).first()
        if banco is None:
            banco = Account(kind="system")
            db.add(banco)
            db.flush()
            creados.append(banco.id)  # si lo creamos nosotros, también se borra
        ids = {}
        for clave, username in nombres.items():
            user = User(username=username, display_name=clave, role="user")
            db.add(user)
            db.flush()
            cuenta = Account(kind="user", user_id=user.id)
            db.add(cuenta)
            db.flush()
            ids[clave] = cuenta.id
        set_balance(db, ids["ana"], 10_000)  # $100
        db.commit()

    barrera = threading.Barrier(2)  # las dos arrancan juntas
    resultados: list[str] = []

    # Peor caso a propósito: después de LEER el saldo, cada hilo espera al otro (máx. 1 s).
    # - Sin bloqueo: los dos leen $100 a la vez → la carrera ocurre SIEMPRE.
    # - Con bloqueo: el segundo está trabado en FOR UPDATE y no llega a leer;
    #   el primero espera 1 s, sigue solo, y la espera se rompe.
    despues_de_leer = threading.Barrier(2, timeout=1.0)

    def get_balance_lento(db: Session, account_id: uuid.UUID) -> int:
        saldo = get_balance(db, account_id)
        try:
            despues_de_leer.wait()
        except threading.BrokenBarrierError:
            pass
        return saldo

    monkeypatch.setattr(ledger, "get_balance", get_balance_lento)

    def mandar(destino: str) -> None:
        with Session(test_engine) as db:
            barrera.wait()
            try:
                transfer(db, ids["ana"], nombres[destino], 8_000)  # $80
                db.commit()
                resultados.append("ok")
            except InsufficientFundsError:
                db.rollback()
                resultados.append("sin saldo")

    hilos = [threading.Thread(target=mandar, args=(d,)) for d in ("luis", "marta")]
    for h in hilos:
        h.start()
    for h in hilos:
        h.join()

    try:
        with Session(test_engine) as db:
            assert sorted(resultados) == ["ok", "sin saldo"]
            assert get_balance(db, ids["ana"]) == 2_000  # $100 - $80
    finally:
        _limpiar(test_engine, list(ids.values()), creados, list(nombres.values()))


def _limpiar(
    engine: Engine,
    account_ids: list[uuid.UUID],
    extra_account_ids: list[uuid.UUID],
    usernames: list[str],
) -> None:
    """Borra lo creado por el test (solo en la base de tests)."""
    with Session(engine) as db:
        tx_ids = db.scalars(
            select(LedgerEntry.transaction_id).where(LedgerEntry.account_id.in_(account_ids))
        ).all()
        db.execute(delete(LedgerEntry).where(LedgerEntry.transaction_id.in_(tx_ids)))
        db.execute(delete(LedgerTransaction).where(LedgerTransaction.id.in_(tx_ids)))
        db.execute(delete(Account).where(Account.id.in_(account_ids + extra_account_ids)))
        db.execute(delete(User).where(User.username.in_(usernames)))
        db.commit()
