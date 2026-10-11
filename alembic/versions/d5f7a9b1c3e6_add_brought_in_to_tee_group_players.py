"""Add brought_in to tee_group_players (BE #251, QA del 11 oct 2026)

Decidido con Agustín el 11 oct 2026: si un no presentado deja a alguien solo en
su partida antes de salir, el último en salir de la siguiente partida de 4 pasa
a acompañarle, y se le avisa en la app. La columna dice quién vino así. Las que
ya existen no vinieron de ninguna parte: falso, por defecto del servidor (cabe
en el guion del modo offline, `alembic upgrade head --sql`).

Revision ID: d5f7a9b1c3e6
Revises: c4e6a8b0d2f5
Create Date: 2026-10-11

"""

import sqlalchemy as sa
from alembic import op

revision = "d5f7a9b1c3e6"
down_revision = "c4e6a8b0d2f5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Quién vino de otra partida a acompañar."""
    op.add_column(
        "tee_group_players",
        sa.Column("brought_in", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    """Quita la columna."""
    op.drop_column("tee_group_players", "brought_in")
