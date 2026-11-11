"""Doble click: el MISMO pedido (misma clave) llega dos veces al mismo tiempo.

Tiene que salir una sola transferencia, y los dos pedidos tienen que recibir la misma.
Usa commits reales en conexiones separadas y limpia lo que crea.
"""

import threading
import uuid

from sqlalchemy import Engine, delete, func, select
from sqlalchemy.orm import Session

from app.models import Account, IdempotencyKey, LedgerEntry, LedgerTransaction, User
from app.services.idempotency import idempotent_transfer
from app.services.ledger import get_balance, set_balance


def test_doble_click_simultaneo_cobra_una_vez(test_engine: Engine) -> None:
    sufijo = uuid.uuid4().hex[:8]
    nombres = {"ana": f"ana-{sufijo}", "luis": f"luis-{sufijo}"}
    extra: list[uuid.UUID] = []

    with Session(test_engine) as db:
        if db.scalars(select(Account).where(Account.kind == "system")).first() is None:
            banco = Account(kind="system")
            db.add(banco)
            db.flush()
            extra.append(banco.id)
        users, cuentas = {}, {}
        for clave, username in nombres.items():
            u = User(username=username, display_name=clave, role="user")
            db.add(u)
            db.flush()
            c = Account(kind="user", user_id=u.id)
            db.add(c)
            db.flush()
            users[clave], cuentas[clave] = u.id, c.id
        set_balance(db, cuentas["ana"], 100_000)
        db.commit()

    barrera = threading.Barrier(2)
    tx_ids: list[uuid.UUID] = []
    errores: list[Exception] = []

    def click() -> None:
        with Session(test_engine) as db:
            barrera.wait()
            try:
                tx, _ = idempotent_transfer(
                    db, users["ana"], cuentas["ana"], "doble-click-1", nombres["luis"], 10_000
                )
                db.commit()
                tx_ids.append(tx.id)
            except Exception as error:  # noqa: BLE001 - queremos ver cualquier error
                errores.append(error)

    hilos = [threading.Thread(target=click) for _ in range(2)]
    for h in hilos:
        h.start()
    for h in hilos:
        h.join()

    try:
        assert errores == []
        assert len(tx_ids) == 2 and tx_ids[0] == tx_ids[1]
        with Session(test_engine) as db:
            assert get_balance(db, cuentas["ana"]) == 90_000
            n = db.scalar(
                select(func.count())
                .select_from(LedgerEntry)
                .where(LedgerEntry.account_id == cuentas["luis"])
            )
            assert n == 1
    finally:
        with Session(test_engine) as db:
            ids = list(cuentas.values())
            tx = db.scalars(
                select(LedgerEntry.transaction_id).where(LedgerEntry.account_id.in_(ids))
            ).all()
            db.execute(delete(IdempotencyKey).where(IdempotencyKey.user_id.in_(users.values())))
            db.execute(delete(LedgerEntry).where(LedgerEntry.transaction_id.in_(tx)))
            db.execute(delete(LedgerTransaction).where(LedgerTransaction.id.in_(tx)))
            db.execute(delete(Account).where(Account.id.in_(ids + extra)))
            db.execute(delete(User).where(User.id.in_(users.values())))
            db.commit()
