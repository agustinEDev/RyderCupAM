"""enrollment entered waiting, for the direct entry in public competitions

Release social 3 (tabla del 28 oct 2026): en una publica se entra directamente,
y en un stroke play con franjas se puede entrar apuntandose a la espera de una
franja llena. Quien entro asi y se queda sin plaza y sin espera (deja su ultima
espera, se borra la franja o se cierran las inscripciones) sale de la
competicion. Quien entro por invitacion o a mano sin franja, no: el organizador
lo coloca. Hace falta saber como entro cada uno.

Una columna booleana con valor por defecto: en Postgres 11+ no reescribe la
tabla, va en la transaccion.

Revision ID: b4d6f8a0c2e5
Revises: a1c3e5f7b9d2
Create Date: 2026-10-28

"""

import sqlalchemy as sa
from alembic import op

revision = "b4d6f8a0c2e5"
down_revision = "a1c3e5f7b9d2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "enrollments",
        sa.Column("entered_waiting", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("enrollments", "entered_waiting")
