"""Reinicio diario de la demo: a las 3:00 (Uruguay) cada cuenta vuelve a su saldo inicial.

NO se borra nada (regla "solo agregar"): se agrega UN movimiento `daily_reset` que
lleva cada cuenta a su saldo inicial, con el Banco de juguete como contrapartida.
El historial completo queda en la base; el frontend solo muestra el día actual.
"""

from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.core.demo import INITIAL_BALANCES, RESET_HOUR, TIMEZONE
from app.models import Account, Charge, DailyReset, LedgerEntry, LedgerTransaction, User
from app.services.ledger import get_balance, get_system_account

ZONA = ZoneInfo(TIMEZONE)


def demo_day(now: datetime | None = None) -> date:
    """Qué "día de demo" es. Empieza a las 3:00 de Uruguay: a las 2:59 todavía es "ayer"."""
    local = (now or datetime.now(UTC)).astimezone(ZONA)
    return (local - timedelta(hours=RESET_HOUR)).date()


def next_reset_at(now: datetime | None = None) -> datetime:
    """Cuándo es el próximo reinicio (con zona horaria de Uruguay)."""
    dia = demo_day(now) + timedelta(days=1)
    return datetime(dia.year, dia.month, dia.day, RESET_HOUR, tzinfo=ZONA)


def run_reset(db: Session) -> LedgerTransaction:
    """Lleva cada cuenta a su saldo inicial y vence los cobros pendientes. No hace commit."""
    banco = get_system_account(db)
    cuentas = db.execute(
        select(Account, User.username)
        .join(User, Account.user_id == User.id)
        .where(User.username.in_(INITIAL_BALANCES))
        .order_by(Account.id)
        .with_for_update(of=Account)  # nadie mueve dinero mientras reiniciamos
    ).all()

    tx = LedgerTransaction(kind="daily_reset")
    renglones = []
    for cuenta, username in cuentas:
        diferencia = INITIAL_BALANCES[username] - get_balance(db, cuenta.id)
        if diferencia:
            renglones.append(LedgerEntry(account_id=cuenta.id, amount=diferencia))
    total = sum(r.amount for r in renglones)
    if total:
        renglones.append(LedgerEntry(account_id=banco.id, amount=-total))  # suma cero
    tx.entries = renglones
    db.add(tx)

    db.execute(
        update(Charge)
        .where(Charge.status == "pending")
        .values(status="expired", resolved_at=datetime.now(UTC))
    )
    db.flush()
    return tx


def ensure_daily_reset(db: Session, now: datetime | None = None) -> bool:
    """Si todavía no se reinició el día de demo actual, lo reinicia. No hace commit.

    Se puede llamar muchas veces y desde varios lados a la vez (API, worker):
    la fecha es clave primaria, así que solo UNO gana y reinicia.
    Devuelve True si reinició.
    """
    dia = demo_day(now)
    if db.get(DailyReset, dia) is not None:
        return False
    with db.begin_nested():
        ganamos = db.scalar(
            insert(DailyReset).values(day=dia).on_conflict_do_nothing().returning(DailyReset.day)
        )
        if ganamos is None:
            return False  # otro proceso lo está haciendo (o ya lo hizo)
        tx = run_reset(db)
        db.execute(update(DailyReset).where(DailyReset.day == dia).values(transaction_id=tx.id))
    return True
