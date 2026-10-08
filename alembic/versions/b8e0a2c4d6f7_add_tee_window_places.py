"""Add tee_window_places (BE #251)

La plaza de cada jugador en cada franja de un Stableford o un Medal (decidido el
6-8 oct 2026): una fila por jugador y franja, única. Se borra con la franja, con
la competición o con el usuario.

Revision ID: b8e0a2c4d6f7
Revises: a7d9f1b3c5e6
Create Date: 2026-10-08

"""

import sqlalchemy as sa
from alembic import op

revision = "b8e0a2c4d6f7"
down_revision = "a7d9f1b3c5e6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Una plaza por jugador y franja."""
    op.create_table(
        "tee_window_places",
        sa.Column("id", sa.CHAR(length=36), primary_key=True),
        sa.Column(
            "competition_id",
            sa.CHAR(length=36),
            sa.ForeignKey("competitions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "round_id",
            sa.CHAR(length=36),
            sa.ForeignKey("rounds.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            sa.CHAR(length=36),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("round_id", "user_id", name="uq_tee_window_places_round_user"),
    )
    op.create_index(
        "ix_tee_window_places_competition_id", "tee_window_places", ["competition_id"]
    )


def downgrade() -> None:
    """Quita las plazas."""
    op.drop_index("ix_tee_window_places_competition_id", table_name="tee_window_places")
    op.drop_table("tee_window_places")
