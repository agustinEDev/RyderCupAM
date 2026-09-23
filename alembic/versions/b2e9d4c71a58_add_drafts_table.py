"""add drafts table

La sala de draft (FE #653): los capitanes eligen equipo por turnos, con el
reloj del servidor. Una fila por competicion —la restriccion unica lo dice— y
las elecciones en JSONB dentro de esa misma fila: son pocas, siempre se leen
juntas y nunca se consultan por separado.

Sin datos que convertir: hasta ahora no habia draft.

Revision ID: b2e9d4c71a58
Revises: f1a4c7d29b63
Create Date: 2026-09-23

"""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

revision = "b2e9d4c71a58"
down_revision = "f1a4c7d29b63"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "drafts",
        sa.Column("id", sa.CHAR(36), primary_key=True),
        sa.Column("competition_id", sa.CHAR(36), nullable=False, unique=True),
        # RESTRICT y no SET NULL: una sala sin capitan no existe —son quienes
        # eligen—, asi que borrar a uno con un draft vivo tiene que pararse
        # antes, en el panel de administracion, y no acabar con la fila rota
        sa.Column(
            "team_a_captain_id",
            sa.CHAR(36),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "team_b_captain_id",
            sa.CHAR(36),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("first_pick", sa.String(1), nullable=True),
        sa.Column("current_team", sa.String(1), nullable=True),
        # De aqui sale cuanto queda de turno: el reloj es del servidor (BE #305)
        sa.Column("turn_started_at", sa.DateTime(), nullable=True),
        sa.Column("picks", JSONB, nullable=False, server_default="[]"),
        sa.Column("seconds_per_turn", sa.Integer(), nullable=False, server_default="60"),
        sa.ForeignKeyConstraint(["competition_id"], ["competitions.id"], ondelete="CASCADE"),
    )


def downgrade() -> None:
    op.drop_table("drafts")
