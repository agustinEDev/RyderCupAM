"""Add tee_sheet to rounds (BE #251)

La hoja de salidas de una franja de un Stableford o un Medal (decidido el 6-7
oct 2026): primera y última salida, intervalo y jugadores por partida, de donde
sale el cupo de la franja. NULL en las sesiones de la Ryder.

Revision ID: f6c8e0a2b4d5
Revises: e5b7c9d1f3a6
Create Date: 2026-10-07

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "f6c8e0a2b4d5"
down_revision = "e5b7c9d1f3a6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Añade la hoja de salidas."""
    op.add_column("rounds", sa.Column("tee_sheet", postgresql.JSONB(), nullable=True))


def downgrade() -> None:
    """Quita la hoja de salidas."""
    op.drop_column("rounds", "tee_sheet")
