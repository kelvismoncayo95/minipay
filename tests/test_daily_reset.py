"""Tests del reinicio diario de la demo (3:00 hora de Uruguay)."""

from datetime import UTC, date, datetime, timedelta

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.demo import INITIAL_BALANCES, TOTAL_POOL
from app.models import Account, Charge, LedgerEntry, User
from app.seed import seed_demo
from app.services.charges import create_charge
from app.services.daily_reset import demo_day, ensure_daily_reset, next_reset_at
from app.services.ledger import LimitExceededError, get_balance, transfer

# Uruguay es UTC-3 todo el año: las 3:00 de Uruguay son las 6:00 UTC.
ANTES = datetime(2026, 11, 12, 5, 59, tzinfo=UTC)  # 2:59 en Uruguay
DESPUES = datetime(2026, 11, 12, 6, 0, tzinfo=UTC)  # 3:00 en Uruguay


def test_el_dia_de_demo_empieza_a_las_3_de_uruguay() -> None:
    assert demo_day(ANTES) == date(2026, 11, 11)  # a las 2:59 todavía es "ayer"
    assert demo_day(DESPUES) == date(2026, 11, 12)


def test_proximo_reinicio() -> None:
    assert next_reset_at(ANTES).astimezone(UTC) == DESPUES


def cuenta_de(db: Session, username: str) -> Account:
    return db.scalars(select(Account).join(User, Account.user_id == User.id).where(User.username == username)).one()


@pytest.fixture
def demo(db: Session) -> Session:
    seed_demo(db)
    assert ensure_daily_reset(db, now=ANTES) is True
    return db


def test_el_reinicio_deja_los_saldos_iniciales(demo: Session) -> None:
    for username, saldo in INITIAL_BALANCES.items():
        assert get_balance(demo, cuenta_de(demo, username).id) == saldo
    personas = sum(get_balance(demo, cuenta_de(demo, u).id) for u in INITIAL_BALANCES)
    assert personas == TOTAL_POOL  # US$10.000 en circulación
    assert demo.scalar(select(func.sum(LedgerEntry.amount))) == 0  # el libro cuadra


def test_un_solo_reinicio_por_dia(demo: Session) -> None:
    # Una hora antes (1:59 de Uruguay) sigue siendo el mismo día de demo.
    assert ensure_daily_reset(demo, now=ANTES - timedelta(hours=1)) is False


def test_al_dia_siguiente_todo_vuelve_a_empezar(demo: Session) -> None:
    ana = cuenta_de(demo, "ana").id
    transfer(demo, ana, "luis", 50_000)
    transfer(demo, ana, "luis", 50_000)
    with pytest.raises(LimitExceededError):  # ya mandó US$1.000 hoy
        transfer(demo, ana, "luis", 100)

    assert ensure_daily_reset(demo, now=DESPUES) is True
    assert get_balance(demo, ana) == 250_000
    assert get_balance(demo, cuenta_de(demo, "luis").id) == 250_000
    transfer(demo, ana, "luis", 100)  # el límite diario también se reinició
    assert demo.scalar(select(func.sum(LedgerEntry.amount))) == 0


def test_el_historial_no_se_borra(demo: Session) -> None:
    ana = cuenta_de(demo, "ana").id
    transfer(demo, ana, "luis", 1_000)
    antes = demo.scalar(select(func.count()).select_from(LedgerEntry))
    ensure_daily_reset(demo, now=DESPUES)
    assert demo.scalar(select(func.count()).select_from(LedgerEntry)) > antes


def test_los_cobros_pendientes_vencen(demo: Session) -> None:
    clinica = demo.scalars(select(User).where(User.username == "clinica-del-sur")).one()
    charge = create_charge(demo, clinica, "ana", 1_000, "Consulta")
    ensure_daily_reset(demo, now=DESPUES)
    demo.refresh(charge)
    assert charge.status == "expired"
    assert demo.get(Charge, charge.id).resolved_at is not None
