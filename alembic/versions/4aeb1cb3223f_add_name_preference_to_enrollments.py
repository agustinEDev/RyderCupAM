"""add name preference to enrollments

Desde #239 el alias sustituye el nombre en todas partes, competiciones
incluidas: la clasificación, la anotación, la lista de inscritos. Es lo
correcto en una partida entre amigos, pero un torneo de club tiene lista de
salida y clasificación pública, y ahí un jugador puede preferir su nombre
legal (BE #254).

`use_real_name` es por INSCRIPCIÓN, no del perfil ni una sola vez por
usuario: la misma persona puede jugar un torneo de club con su nombre legal
y una liguilla de amigos con su alias, la misma semana.

`false` por defecto — se sigue enseñando el alias, que es el comportamiento
de antes de esta migración — y NOT NULL: no hay un tercer estado «sin
decidir» que resolver en cada lectura.

Revision ID: 4aeb1cb3223f
Revises: c8e1d5b73f92
Create Date: 2026-09-03

"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "4aeb1cb3223f"
down_revision = "c8e1d5b73f92"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "enrollments",
        sa.Column("use_real_name", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("enrollments", "use_real_name")
