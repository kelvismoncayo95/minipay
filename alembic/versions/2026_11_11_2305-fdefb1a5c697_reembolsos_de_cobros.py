"""reembolsos de cobros

Revision ID: fdefb1a5c697
Revises: c8bde2ba7083
Create Date: 2026-11-11 23:05:00

Corregida a mano: autogenerate dejó la clave foránea sin nombre (el downgrade no
podría borrarla) y no detecta cambios dentro de los CHECK.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'fdefb1a5c697'
down_revision: Union[str, None] = 'c8bde2ba7083'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

FK = 'charges_refund_transaction_id_fkey'


def upgrade() -> None:
    op.add_column('charges', sa.Column('refund_transaction_id', sa.Uuid(), nullable=True))
    op.add_column('charges', sa.Column('refunded_at', sa.DateTime(timezone=True), nullable=True))
    op.create_foreign_key(FK, 'charges', 'ledger_transactions', ['refund_transaction_id'], ['id'])

    _cambiar_check('ledger_transactions', 'ck_ledger_transactions_kind',
                   "kind IN ('balance_set', 'transfer', 'payment', 'daily_reset', 'refund')")
    _cambiar_check('charges', 'ck_charges_status',
                   "status IN ('pending', 'paid', 'rejected', 'expired', 'refunded')")
    _cambiar_check('charges', 'ck_charges_paid_has_transaction',
                   "(status IN ('paid', 'refunded')) = (transaction_id IS NOT NULL)")
    op.create_check_constraint('ck_charges_refund_has_transaction', 'charges',
                               "(status = 'refunded') = (refund_transaction_id IS NOT NULL)")


def downgrade() -> None:
    # Ojo: falla si ya hay reembolsos (no se borran datos del libro a propósito).
    op.drop_constraint('ck_charges_refund_has_transaction', 'charges', type_='check')
    _cambiar_check('charges', 'ck_charges_paid_has_transaction',
                   "(status = 'paid') = (transaction_id IS NOT NULL)")
    _cambiar_check('charges', 'ck_charges_status',
                   "status IN ('pending', 'paid', 'rejected', 'expired')")
    _cambiar_check('ledger_transactions', 'ck_ledger_transactions_kind',
                   "kind IN ('balance_set', 'transfer', 'payment', 'daily_reset')")
    op.drop_constraint(FK, 'charges', type_='foreignkey')
    op.drop_column('charges', 'refunded_at')
    op.drop_column('charges', 'refund_transaction_id')


def _cambiar_check(tabla: str, nombre: str, condicion: str) -> None:
    op.drop_constraint(nombre, tabla, type_='check')
    op.create_check_constraint(nombre, tabla, condicion)
