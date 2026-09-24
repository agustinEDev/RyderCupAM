"""Add match_generation_block to rounds (BE #361)

Los partidos se crean al abrirse los sobres. Si no se pueden crear —a un
jugador le falta el sexo, el campo no tiene su color de barras—, la sesion se
queda con los sobres abiertos y sin partidos, y el motivo se apunta aqui para
que el organizador lo vea: a quien le falta que.

NULL es «no hay motivo», asi que las rondas que ya existen no necesitan nada.

Revision ID: e4b7c2d91f36
Revises: d8e2f4a19c73
Create Date: 2026-09-24

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "e4b7c2d91f36"
down_revision = "d8e2f4a19c73"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Anade el motivo a la ronda."""
    op.add_column(
        "rounds",
        sa.Column("match_generation_block", postgresql.JSONB, nullable=True),
    )


def downgrade() -> None:
    """Quita el motivo."""
    op.drop_column("rounds", "match_generation_block")
