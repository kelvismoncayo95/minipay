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


# ---------- Límites separados: pagos a comercios (decidido 2026-11-11) ----------


def test_limites_de_pagos() -> None:
    from app.core.demo import DAILY_PAYMENT_LIMIT, MAX_PAYMENT

    assert MAX_PAYMENT == 100_000  # US$1.000 por cobro
    assert DAILY_PAYMENT_LIMIT == 200_000  # US$2.000 pagados por día


def test_transferir_no_quita_margen_para_pagar(db: Session, cuentas: dict[str, Account]) -> None:
    from app.services.ledger import move_money

    db.add(Account(kind="user", user_id=_comercio(db).id))
    db.flush()
    ana = cuentas["ana"].id
    set_balance(db, ana, 300_000)
    transfer(db, ana, "luis", 50_000)
    transfer(db, ana, "luis", 50_000)  # límite de transferencias del día: lleno
    clinica = _cuenta_comercio(db)
    move_money(db, ana, clinica, 100_000, kind="payment")  # pagar sigue permitido
    assert get_balance(db, ana) == 100_000


def test_limite_diario_de_pagos(db: Session, cuentas: dict[str, Account]) -> None:
    from app.services.ledger import move_money

    db.add(Account(kind="user", user_id=_comercio(db).id))
    db.flush()
    ana, clinica = cuentas["ana"].id, _cuenta_comercio(db)
    set_balance(db, ana, 300_000)
    move_money(db, ana, clinica, 100_000, kind="payment")
    move_money(db, ana, clinica, 100_000, kind="payment")  # US$2.000: justo el límite
    with pytest.raises(LimitExceededError):
        move_money(db, ana, clinica, 100, kind="payment")


def test_maximo_por_pago(db: Session, cuentas: dict[str, Account]) -> None:
    from app.services.ledger import move_money

    db.add(Account(kind="user", user_id=_comercio(db).id))
    db.flush()
    set_balance(db, cuentas["ana"].id, 300_000)
    with pytest.raises(LimitExceededError):
        move_money(db, cuentas["ana"].id, _cuenta_comercio(db), 100_001, kind="payment")


def _comercio(db: Session) -> User:
    from sqlalchemy import select

    existente = db.scalars(select(User).where(User.username == "clinica-del-sur")).first()
    if existente:
        return existente
    user = User(username="clinica-del-sur", display_name="Clínica", role="merchant")
    db.add(user)
    db.flush()
    return user


def _cuenta_comercio(db: Session):
    from sqlalchemy import select

    return db.scalars(select(Account.id).where(Account.user_id == _comercio(db).id)).one()
