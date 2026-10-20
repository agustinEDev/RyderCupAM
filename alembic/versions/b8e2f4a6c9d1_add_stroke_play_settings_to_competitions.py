"""Add stroke play settings to competitions (BE #251)

Decidido con Agustín el 6 oct 2026: un Stableford o un Medal lleva sus límites
de categoría, en cuántas jornadas juega cada jugador y cómo se calcula la
general. Una Ryder Cup no los tiene: sus tres columnas quedan vacías.

Los Stableford y Medal que ya existan (se pueden crear por la API desde la
BE #480) reciben los valores por defecto: sin categorías, una jornada por
jugador y la general acumulada. Es un UPDATE sin lecturas, así que cabe también
en el guion del modo offline (`alembic upgrade head --sql`).

Revision ID: b8e2f4a6c9d1
Revises: a7d3e9f2c4b1
Create Date: 2026-10-06

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "b8e2f4a6c9d1"
down_revision = "a7d3e9f2c4b1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Añade los ajustes del stroke play y rellena los torneos de stroke play que haya."""
    op.add_column(
        "competitions",
        sa.Column(
            "stroke_category_limits",
            postgresql.ARRAY(sa.Numeric(precision=4, scale=1)),
            nullable=True,
        ),
    )
    op.add_column(
        "competitions",
        sa.Column("stroke_max_matchdays_per_player", sa.Integer(), nullable=True),
    )
    op.add_column(
        "competitions",
        sa.Column("stroke_overall_standing", sa.String(20), nullable=True),
    )
    op.execute(
        "UPDATE competitions "
        "SET stroke_category_limits = '{}', "
        "stroke_max_matchdays_per_player = 1, "
        "stroke_overall_standing = 'ACCUMULATED' "
        "WHERE tournament_type IN ('STABLEFORD', 'MEDAL')"
    )


def downgrade() -> None:
    """Quita los ajustes del stroke play."""
    op.drop_column("competitions", "stroke_overall_standing")
    op.drop_column("competitions", "stroke_max_matchdays_per_player")
    op.drop_column("competitions", "stroke_category_limits")
