"""Idempotencia: si el mismo pedido llega dos veces, se procesa una sola.

El cliente manda una clave única por pedido (header `Idempotency-Key`).
- Clave nueva → se hace la operación y se guarda la clave con el resultado.
- Clave ya usada con el MISMO pedido → se devuelve el resultado guardado (no se cobra de nuevo).
- Clave ya usada con OTRO pedido → error (el cliente se equivocó).
"""

import hashlib
import uuid
from collections.abc import Callable

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.models import IdempotencyKey, LedgerTransaction
from app.services.ledger import transfer


class IdempotencyConflictError(ValueError):
    """La clave ya se usó para un pedido distinto."""


def fingerprint(*partes: object) -> str:
    """Huella del pedido: mismo contenido → misma huella."""
    return hashlib.sha256("|".join(str(p) for p in partes).encode()).hexdigest()


def run_idempotent(
    db: Session,
    user_id: uuid.UUID,
    key: str,
    request_hash: str,
    action: Callable[[], LedgerTransaction],
) -> tuple[LedgerTransaction, bool]:
    """Ejecuta `action` una sola vez por (usuario, clave).

    Devuelve (movimiento, repetido). `repetido` es True si se devolvió el guardado.
    No hace commit.
    """
    # Savepoint: si `action` falla, se deshace también la clave (se puede reintentar).
    with db.begin_nested():
        # INSERT ... ON CONFLICT DO NOTHING: si otra transacción está insertando la misma
        # clave, PostgreSQL hace ESPERAR a esta hasta que la otra termine. Sin carreras.
        nueva = db.scalar(
            insert(IdempotencyKey)
            .values(id=uuid.uuid4(), user_id=user_id, key=key, request_hash=request_hash)
            .on_conflict_do_nothing(constraint="uq_idempotency_keys_user_key")
            .returning(IdempotencyKey.id)
        )
        if nueva is not None:
            tx = action()
            db.execute(
                update(IdempotencyKey)
                .where(IdempotencyKey.id == nueva)
                .values(transaction_id=tx.id)
            )
            return tx, False

    guardada = db.scalars(
        select(IdempotencyKey).where(IdempotencyKey.user_id == user_id, IdempotencyKey.key == key)
    ).one()
    if guardada.request_hash != request_hash:
        raise IdempotencyConflictError("Esa Idempotency-Key ya se usó para otro pedido.")
    return db.get(LedgerTransaction, guardada.transaction_id), True


def idempotent_transfer(
    db: Session,
    user_id: uuid.UUID,
    from_account_id: uuid.UUID,
    key: str,
    to_username: str,
    amount: int,
) -> tuple[LedgerTransaction, bool]:
    """Transferencia protegida contra pedidos repetidos."""
    return run_idempotent(
        db,
        user_id,
        key,
        fingerprint("transfer", to_username, amount),
        lambda: transfer(db, from_account_id, to_username, amount),
    )
