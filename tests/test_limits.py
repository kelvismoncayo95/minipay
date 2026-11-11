"""Tests de límites de la demo (fondo fijo: US$500 por operación, US$1.000 por día)."""

import pytest
from sqlalchemy.orm import Session

from app.models import Account, User
from app.services.ledger import (
    BALANCE_CHANGES_PER_HOUR,
    DAILY_TRANSFER_LIMIT,
    MAX_TRANSFER,
    LimitExceededError,
    RateLimitError,
    dinero,
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
    assert MAX_TRANSFER == 50_000  # US$500
    assert DAILY_TRANSFER_LIMIT == 100_000  # US$1.000
    assert BALANCE_CHANGES_PER_HOUR == 5


def test_maximo_por_operacion(db: Session, cuentas: dict[str, Account]) -> None:
    set_balance(db, cuentas["ana"].id, 100_000)
    with pytest.raises(LimitExceededError):
        transfer(db, cuentas["ana"].id, "luis", 50_001)
    transfer(db, cuentas["ana"].id, "luis", 50_000)  # justo el máximo: sí
    assert get_balance(db, cuentas["ana"].id) == 50_000


def test_limite_diario(db: Session, cuentas: dict[str, Account]) -> None:
    ana = cuentas["ana"].id
    set_balance(db, ana, 200_000)
    transfer(db, ana, "luis", 50_000)
    transfer(db, ana, "luis", 50_000)  # US$1.000 en el día: justo el límite
    with pytest.raises(LimitExceededError):
        transfer(db, ana, "luis", 100)  # un centavo más ya pasa
    assert get_balance(db, ana) == 100_000


def test_recibir_no_cuenta_para_el_limite(db: Session, cuentas: dict[str, Account]) -> None:
    ana, luis = cuentas["ana"].id, cuentas["luis"].id
    set_balance(db, ana, 100_000)
    transfer(db, ana, "luis", 50_000)
    transfer(db, ana, "luis", 50_000)
    # Luis recibió US$1.000 pero no mandó nada: puede mandar.
    transfer(db, luis, "ana", 50_000)


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


def test_mensajes_en_dolares() -> None:
    assert dinero(50_000) == "US$500"
    assert dinero(4_550) == "US$45,50"
    assert dinero(100) == "US$1"
    assert dinero(100_000) == "US$1.000"
