"""Add card_status to tee_group_players (BE #251, PR 5)

La tarjeta de cada jugador de una partida: en juego, entregada, retirado o no
presentado (decidido el 9 oct 2026, P3 y P6). Las partidas aún no han llegado
a producción: la columna nace NOT NULL sin rellenar nada.

Revision ID: f2c4e6a8b0d1
Revises: e1b3d5f7a9c2
Create Date: 2026-10-09

"""

import sqlalchemy as sa
from alembic import op

revision = "f2c4e6a8b0d1"
down_revision = "e1b3d5f7a9c2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """El estado de la tarjeta de cada jugador."""
    op.add_column(
        "tee_group_players",
        sa.Column("card_status", sa.String(length=20), nullable=False),
    )


def downgrade() -> None:
    """Quita el estado de la tarjeta."""
    op.drop_column("tee_group_players", "card_status")
