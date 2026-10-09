"""Add pars_by_hole to tee_group_players (BE #251, PR 5)

El par de cada hoyo desde las barras de cada jugador, en la foto de su
partida (decidido el 9 oct 2026, P12): 25 campos federados tienen par distinto
según la barra, y si alguien edita el campo durante la competición los
resultados no deben cambiar. Sin él no hay puntos Stableford ni «par» en Medal.

Las partidas aún no han llegado a producción (PR 4 solo en develop): la
columna nace NOT NULL sin rellenar nada.

Revision ID: e1b3d5f7a9c2
Revises: d0a2c4e6f8b1
Create Date: 2026-10-09

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "e1b3d5f7a9c2"
down_revision = "d0a2c4e6f8b1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """El par por hoyo de cada jugador de una partida."""
    op.add_column(
        "tee_group_players",
        sa.Column("pars_by_hole", postgresql.JSONB(), nullable=False),
    )


def downgrade() -> None:
    """Quita el par por hoyo."""
    op.drop_column("tee_group_players", "pars_by_hole")
