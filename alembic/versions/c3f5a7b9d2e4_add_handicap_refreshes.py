"""Add handicap_refreshes (BE #502)

Lo que pasó al preguntar a la RFEG por cada jugador a las 3:00 de cada día de
juego: actualizado, no encontrado, sin licencia española o fallido. Una fila
por torneo, día y jugador; un reintento sustituye la anterior.

Revision ID: c3f5a7b9d2e4
Revises: b8e2f4a6c9d1
Create Date: 2026-10-07

"""

import sqlalchemy as sa
from alembic import op

revision = "c3f5a7b9d2e4"
down_revision = "b8e2f4a6c9d1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Crea la tabla de resultados del refresco."""
    op.create_table(
        "handicap_refreshes",
        sa.Column(
            "competition_id",
            sa.CHAR(length=36),
            sa.ForeignKey("competitions.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("play_date", sa.Date(), primary_key=True),
        sa.Column(
            "user_id",
            sa.CHAR(length=36),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("result", sa.String(30), nullable=False),
        sa.Column("refreshed_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    """Quita la tabla de resultados del refresco."""
    op.drop_table("handicap_refreshes")
