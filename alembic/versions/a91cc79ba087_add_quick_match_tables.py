"""Add quick_matches and quick_match_hole_scores tables

Revision ID: a91cc79ba087
Revises: 7cec1e04eb61
Create Date: 2026-07-26 16:00:00.000000

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "a91cc79ba087"
down_revision = "7cec1e04eb61"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "quick_matches",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("creator_id", sa.CHAR(36), nullable=False),
        sa.Column("golf_course_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("match_format", sa.String(20), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="PENDING"),
        sa.Column("participants", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["creator_id"],
            ["users.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["golf_course_id"],
            ["golf_courses.id"],
        ),
    )

    op.create_index(
        "ix_quick_matches_creator_id",
        "quick_matches",
        ["creator_id"],
    )
    op.create_index(
        "ix_quick_matches_status",
        "quick_matches",
        ["status"],
    )
    # GIN index para acelerar la busqueda de "partidas donde participo" (JSONB @>)
    op.execute(
        "CREATE INDEX ix_quick_matches_participants_gin "
        "ON quick_matches USING GIN (participants)"
    )

    op.create_table(
        "quick_match_hole_scores",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("quick_match_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("hole_number", sa.Integer(), nullable=False),
        sa.Column("player_user_id", sa.CHAR(36), nullable=False),
        sa.Column("score", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["quick_match_id"],
            ["quick_matches.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["player_user_id"],
            ["users.id"],
            ondelete="CASCADE",
        ),
        sa.CheckConstraint("hole_number BETWEEN 1 AND 18", name="ck_quick_match_hole_number"),
        sa.CheckConstraint("score BETWEEN 1 AND 15", name="ck_quick_match_hole_score"),
    )

    op.create_index(
        "ix_quick_match_hole_scores_quick_match_id",
        "quick_match_hole_scores",
        ["quick_match_id"],
    )
    # Un unico score por jugador y hoyo (upsert target)
    op.create_unique_constraint(
        "uq_quick_match_hole_player",
        "quick_match_hole_scores",
        ["quick_match_id", "hole_number", "player_user_id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_quick_match_hole_player", "quick_match_hole_scores", type_="unique"
    )
    op.drop_index(
        "ix_quick_match_hole_scores_quick_match_id", table_name="quick_match_hole_scores"
    )
    op.drop_table("quick_match_hole_scores")

    op.execute("DROP INDEX IF EXISTS ix_quick_matches_participants_gin")
    op.drop_index("ix_quick_matches_status", table_name="quick_matches")
    op.drop_index("ix_quick_matches_creator_id", table_name="quick_matches")
    op.drop_table("quick_matches")
