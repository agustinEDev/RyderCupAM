"""add captains to competitions

Los dos capitanes de la competicion, uno por equipo, y sus subcapitanes (BE
#320). Van en la competicion y no en la inscripcion (decidido el 22 sep): asi
«uno por equipo» sale de la forma de la tabla, sin indices parciales ni
coordinar filas. El subcapitan lo elige cada capitan tras el draft, y asciende
si el capitan se va.

Nullable, porque se nombran mas tarde y porque la baja de un capitan deja su
puesto libre. `ON DELETE SET NULL`: borrar un usuario no puede llevarse el
torneo por delante, solo su puesto.

Sin datos que convertir: las competiciones que existen no tienen capitanes.

Revision ID: e4b8c1f92a07
Revises: a3f7d21c65b8
Create Date: 2026-09-22

"""

import sqlalchemy as sa

from alembic import op

revision = "e4b8c1f92a07"
down_revision = "a3f7d21c65b8"
branch_labels = None
depends_on = None

COLUMNAS = (
    "team_a_captain_id",
    "team_b_captain_id",
    "team_a_vice_captain_id",
    "team_b_vice_captain_id",
)


def upgrade() -> None:
    for columna in COLUMNAS:
        op.add_column(
            "competitions",
            sa.Column(
                columna,
                # Como `users.id`: CHAR(36), no UUID nativo
                sa.CHAR(length=36),
                sa.ForeignKey("users.id", ondelete="SET NULL"),
                nullable=True,
            ),
        )


def downgrade() -> None:
    for columna in reversed(COLUMNAS):
        op.drop_column("competitions", columna)
