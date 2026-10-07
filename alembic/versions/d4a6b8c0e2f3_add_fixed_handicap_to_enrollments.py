"""Add fixed_handicap and fixed_category to enrollments (BE #251)

El hándicap de todo el torneo de un jugador de un Stableford o un Medal, fijado
al cerrar las inscripciones, como hace la RFEG (decidido el 7 oct 2026): de él
sale su categoría (con la regla de los seis), que se guarda a la vez y ya no
cambia, aunque luego alguien se retire. Vacío mientras las inscripciones están
abiertas, y siempre en una Ryder Cup.

Revision ID: d4a6b8c0e2f3
Revises: c3f5a7b9d2e4
Create Date: 2026-10-07

"""

import sqlalchemy as sa
from alembic import op

revision = "d4a6b8c0e2f3"
down_revision = "c3f5a7b9d2e4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Añade el hándicap fijado."""
    op.add_column(
        "enrollments",
        sa.Column("fixed_handicap", sa.Numeric(precision=4, scale=1), nullable=True),
    )
    op.add_column("enrollments", sa.Column("fixed_category", sa.Integer(), nullable=True))


def downgrade() -> None:
    """Quita el hándicap fijado."""
    op.drop_column("enrollments", "fixed_category")
    op.drop_column("enrollments", "fixed_handicap")
