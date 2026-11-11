"""Tests de límites de la demo (paso 8)."""

import pytest
from sqlalchemy.orm import Session

from app.models import Account, User
from app.services.ledger import (
    BALANCE_CHANGES_PER_HOUR,
    DAILY_TRANSFER_LIMIT,
    MAX_TRANSFER,
    LimitExceededError,
    RateLimitError,
    get_balance,
    set_balance,
    transfer,
)


def crear(db: Session, username: str) -> Account:
    user = User(username=username, display_name=username.title(), role="user")
    db.add(user)
    db.flush()
    cuenta = Account(kind="user", user_id=user.id)
    db.add(cuenta)
    db.flush()
    return cuenta


@pytest.fixture
def cuentas(db: Session) -> dict[str, Account]:
    db.add(Account(kind="system"))
    db.flush()
    return {"ana": crear(db, "ana"), "luis": crear(db, "luis")}


def test_limites_de_la_demo() -> None:
    assert MAX_TRANSFER == 500_000  # $5.000
    assert DAILY_TRANSFER_LIMIT == 1_000_000  # $10.000
    assert BALANCE_CHANGES_PER_HOUR == 5


def test_maximo_por_operacion(db: Session, cuentas: dict[str, Account]) -> None:
    set_balance(db, cuentas["ana"].id, 500_000)
    with pytest.raises(LimitExceededError):
        transfer(db, cuentas["ana"].id, "luis", 500_001)
    transfer(db, cuentas["ana"].id, "luis", 500_000)  # justo el máximo: sí
    assert get_balance(db, cuentas["ana"].id) == 0


def test_limite_diario(db: Session, cuentas: dict[str, Account]) -> None:
    ana = cuentas["ana"].id
    for _ in range(2):  # $5.000 + $5.000 = $10.000 en el día
        set_balance(db, ana, 500_000)
        transfer(db, ana, "luis", 500_000)
    set_balance(db, ana, 500_000)
    with pytest.raises(LimitExceededError):
        transfer(db, ana, "luis", 100)  # un peso más ya pasa el límite
    assert get_balance(db, ana) == 500_000


def test_recibir_no_cuenta_para_el_limite(db: Session, cuentas: dict[str, Account]) -> None:
    ana, luis = cuentas["ana"].id, cuentas["luis"].id
    for _ in range(2):
        set_balance(db, ana, 500_000)
        transfer(db, ana, "luis", 500_000)
    # Luis recibió $10.000 pero no mandó nada: puede mandar.
    transfer(db, luis, "ana", 100_000)


def test_cinco_cambios_de_saldo_por_hora(db: Session, cuentas: dict[str, Account]) -> None:
    ana = cuentas["ana"].id
    for monto in (100, 200, 300, 400, 500):
        set_balance(db, ana, monto)
    with pytest.raises(RateLimitError):
        set_balance(db, ana, 600)
    assert get_balance(db, ana) == 500


def test_elegir_el_mismo_saldo_no_gasta_un_cambio(
    db: Session, cuentas: dict[str, Account]
) -> None:
    ana = cuentas["ana"].id
    for monto in (100, 200, 300, 400, 500):
        set_balance(db, ana, monto)
    assert set_balance(db, ana, 500) is None  # no cambia nada → no cuenta ni falla
