"""Add hole_scores table and match scoring columns

Revision ID: a3d5e7f1b2c4
Revises: f6b8c4d2e3a5
Create Date: 2026-02-20 18:00:00.000000

"""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

# revision identifiers, used by Alembic.
revision = "a3d5e7f1b2c4"
down_revision = "f6b8c4d2e3a5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- New table: hole_scores ---
    op.create_table(
        "hole_scores",
        sa.Column("id", sa.CHAR(36), nullable=False),
        sa.Column("match_id", sa.CHAR(36), nullable=False),
        sa.Column("hole_number", sa.Integer(), nullable=False),
        sa.Column("player_user_id", sa.CHAR(36), nullable=False),
        sa.Column("team", sa.String(1), nullable=False),
        sa.Column("own_score", sa.Integer(), nullable=True),
        sa.Column("own_submitted", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("marker_score", sa.Integer(), nullable=True),
        sa.Column("marker_submitted", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("strokes_received", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("net_score", sa.Integer(), nullable=True),
        sa.Column("validation_status", sa.String(20), nullable=False, server_default="PENDING"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["match_id"],
            ["matches.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["player_user_id"],
            ["users.id"],
            ondelete="CASCADE",
        ),
    )

    # Unique constraint: one score per player per hole per match
    op.create_unique_constraint(
        "uq_hole_score_match_hole_player",
        "hole_scores",
        ["match_id", "hole_number", "player_user_id"],
    )

    # Index for frequent queries
    op.create_index(
        "ix_hole_scores_match_id",
        "hole_scores",
        ["match_id"],
    )

    # --- New columns on matches table ---
    op.add_column(
        "matches",
        sa.Column("marker_assignments", JSONB(), nullable=True),
    )
    op.add_column(
        "matches",
        sa.Column("scorecard_submitted_by", JSONB(), nullable=True),
    )
    op.add_column(
        "matches",
        sa.Column("is_decided", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.add_column(
        "matches",
        sa.Column("decided_result", JSONB(), nullable=True),
    )


def downgrade() -> None:
    # Remove matches columns
    op.drop_column("matches", "decided_result")
    op.drop_column("matches", "is_decided")
    op.drop_column("matches", "scorecard_submitted_by")
    op.drop_column("matches", "marker_assignments")

    # Remove hole_scores table
    op.drop_index("ix_hole_scores_match_id", table_name="hole_scores")
    op.drop_constraint("uq_hole_score_match_hole_player", "hole_scores", type_="unique")
    op.drop_table("hole_scores")
