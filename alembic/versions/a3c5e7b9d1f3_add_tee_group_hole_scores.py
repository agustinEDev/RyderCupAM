"""Add tee_group_hole_scores (BE #251, PR 5)

Los golpes de los jugadores de las partidas de stroke play: un hoyo por fila,
con el lado del jugador (o del organizador por él), el del marcador y quién
metió cada uno (decisión 11 de la #251; P9 del 9 oct 2026). Sin id propio: la
cola sin conexión del móvil los identifica por partida, jugador y hoyo.

La clave ajena a su jugador se comprueba al final de la transacción: el
repositorio de partidas reescribe sus jugadores al guardar, y una partida con
golpes no se puede borrar.

No es `hole_scores` de la Ryder: aquella cuelga de un partido y de un equipo, y
la leen estadísticas y logros.

Revision ID: a3c5e7b9d1f3
Revises: f2c4e6a8b0d1
Create Date: 2026-10-09

"""

import sqlalchemy as sa
from alembic import op

revision = "a3c5e7b9d1f3"
down_revision = "f2c4e6a8b0d1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """La tabla de golpes de las partidas."""
    op.create_table(
        "tee_group_hole_scores",
        sa.Column("group_id", sa.CHAR(length=36), primary_key=True),
        sa.Column("user_id", sa.CHAR(length=36), primary_key=True),
        sa.Column("hole_number", sa.Integer(), primary_key=True),
        sa.Column("round_id", sa.CHAR(length=36), nullable=False),
        sa.Column("competition_id", sa.CHAR(length=36), nullable=False),
        sa.Column("own_score", sa.Integer(), nullable=True),
        sa.Column("own_submitted", sa.Boolean(), nullable=False),
        sa.Column("own_by", sa.CHAR(length=36), nullable=True),
        sa.Column("marker_score", sa.Integer(), nullable=True),
        sa.Column("marker_submitted", sa.Boolean(), nullable=False),
        sa.Column("marker_by", sa.CHAR(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("hole_number BETWEEN 1 AND 18", name="ck_tee_group_hole_scores_hole"),
        sa.CheckConstraint(
            "own_score IS NULL OR own_score BETWEEN 1 AND 15", name="ck_tee_group_hole_scores_own"
        ),
        sa.CheckConstraint(
            "marker_score IS NULL OR marker_score BETWEEN 1 AND 15",
            name="ck_tee_group_hole_scores_marker",
        ),
        sa.ForeignKeyConstraint(
            ["group_id", "user_id"],
            ["tee_group_players.group_id", "tee_group_players.user_id"],
            name="fk_tee_group_hole_scores_player",
            deferrable=True,
            initially="DEFERRED",
        ),
    )
    op.create_index(
        "ix_tee_group_hole_scores_round_id", "tee_group_hole_scores", ["round_id"]
    )
    op.create_index(
        "ix_tee_group_hole_scores_competition_id", "tee_group_hole_scores", ["competition_id"]
    )


def downgrade() -> None:
    """Quita los golpes de las partidas."""
    op.drop_index("ix_tee_group_hole_scores_competition_id", table_name="tee_group_hole_scores")
    op.drop_index("ix_tee_group_hole_scores_round_id", table_name="tee_group_hole_scores")
    op.drop_table("tee_group_hole_scores")
