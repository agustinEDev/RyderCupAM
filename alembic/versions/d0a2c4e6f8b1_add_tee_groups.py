"""Add tee_groups and tee_group_players (BE #251, PR 4)

Las partidas de las franjas de un Stableford o un Medal (decidido el 6-9 oct
2026): cada partida con su número de salida (la hora sale de la hoja de
salidas, no se guarda) y cada jugador con la foto que se sacó al generar.

Los únicos de número y de jugador se comprueban al final de la transacción:
un intercambio o un reordenado los repite a medias.

Revision ID: d0a2c4e6f8b1
Revises: c9f1b3d5e7a8
Create Date: 2026-10-09

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "d0a2c4e6f8b1"
down_revision = "c9f1b3d5e7a8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Las partidas y sus jugadores."""
    op.create_table(
        "tee_groups",
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
        sa.Column("number", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("number >= 1", name="ck_tee_groups_number_positive"),
        sa.UniqueConstraint(
            "round_id",
            "number",
            name="uq_tee_groups_round_number",
            deferrable=True,
            initially="DEFERRED",
        ),
        sa.UniqueConstraint("id", "round_id", name="uq_tee_groups_id_round"),
    )
    op.create_index("ix_tee_groups_competition_id", "tee_groups", ["competition_id"])
    op.create_table(
        "tee_group_players",
        sa.Column("group_id", sa.CHAR(length=36), primary_key=True),
        sa.Column("round_id", sa.CHAR(length=36), nullable=False),
        sa.Column(
            "user_id",
            sa.CHAR(length=36),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            primary_key=True,
        ),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("handicap_index", sa.Numeric(precision=4, scale=1), nullable=False),
        sa.Column("playing_handicap", sa.Integer(), nullable=False),
        sa.Column("tee_color", sa.String(length=20), nullable=False),
        sa.Column("tee_gender", sa.String(length=20), nullable=True),
        sa.Column("strokes_by_hole", postgresql.JSONB(), nullable=False),
        sa.Column(
            "marks_user_id",
            sa.CHAR(length=36),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.ForeignKeyConstraint(
            ["group_id", "round_id"],
            ["tee_groups.id", "tee_groups.round_id"],
            name="fk_tee_group_players_group",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "round_id",
            "user_id",
            name="uq_tee_group_players_round_user",
            deferrable=True,
            initially="DEFERRED",
        ),
        sa.UniqueConstraint(
            "group_id",
            "position",
            name="uq_tee_group_players_group_position",
            deferrable=True,
            initially="DEFERRED",
        ),
    )
    op.create_index("ix_tee_group_players_user_id", "tee_group_players", ["user_id"])


def downgrade() -> None:
    """Quita las partidas."""
    op.drop_index("ix_tee_group_players_user_id", table_name="tee_group_players")
    op.drop_table("tee_group_players")
    op.drop_index("ix_tee_groups_competition_id", table_name="tee_groups")
    op.drop_table("tee_groups")
