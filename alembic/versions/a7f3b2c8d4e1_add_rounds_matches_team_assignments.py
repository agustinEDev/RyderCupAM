"""add rounds, matches, team_assignments tables + enrollment fixes

Revision ID: a7f3b2c8d4e1
Revises: 2b72b9741fd1
Create Date: 2026-02-05 20:00:00.000000

Sprint 2 Block 5 - Infrastructure Layer for Rounds, Matches, TeamAssignment.
Also adds tee_category to enrollments.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID


# revision identifiers, used by Alembic.
revision: str = "a7f3b2c8d4e1"
down_revision: Union[str, None] = "2b72b9741fd1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # =========================================================================
    # 1. DB Fixes - Enrollment table
    # =========================================================================

    # Add tee_category column (already in domain entity, missing in DB)
    op.add_column(
        "enrollments",
        sa.Column("tee_category", sa.String(20), nullable=True),
    )

    # =========================================================================
    # 2. New table: rounds
    # =========================================================================

    op.create_table(
        "rounds",
        sa.Column("id", sa.CHAR(length=36), nullable=False),
        sa.Column("competition_id", sa.CHAR(length=36), nullable=False),
        sa.Column("golf_course_id", UUID(as_uuid=True), nullable=False),
        sa.Column("round_date", sa.Date(), nullable=False),
        sa.Column("session_type", sa.String(20), nullable=False),
        sa.Column("match_format", sa.String(20), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("handicap_mode", sa.String(20), nullable=True),
        sa.Column("allowance_percentage", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        # Primary Key
        sa.PrimaryKeyConstraint("id", name="pk_rounds"),
        # Foreign Keys
        sa.ForeignKeyConstraint(
            ["competition_id"],
            ["competitions.id"],
            name="fk_rounds_competition_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["golf_course_id"],
            ["golf_courses.id"],
            name="fk_rounds_golf_course_id",
            ondelete="RESTRICT",
        ),
        # Unique Constraints
        sa.UniqueConstraint(
            "competition_id",
            "round_date",
            "session_type",
            name="uq_rounds_competition_date_session",
        ),
        # Check Constraints
        sa.CheckConstraint(
            "allowance_percentage >= 50 AND allowance_percentage <= 100",
            name="ck_rounds_allowance_percentage_range",
        ),
    )

    # Indexes for rounds
    op.create_index("ix_rounds_competition_id", "rounds", ["competition_id"])
    op.create_index("ix_rounds_golf_course_id", "rounds", ["golf_course_id"])
    op.create_index("ix_rounds_status", "rounds", ["status"])
    op.create_index(
        "ix_rounds_competition_id_status",
        "rounds",
        ["competition_id", "status"],
    )

    # =========================================================================
    # 3. New table: matches
    # =========================================================================

    op.create_table(
        "matches",
        sa.Column("id", sa.CHAR(length=36), nullable=False),
        sa.Column("round_id", sa.CHAR(length=36), nullable=False),
        sa.Column("match_number", sa.Integer(), nullable=False),
        sa.Column("team_a_players", JSONB(), nullable=False),
        sa.Column("team_b_players", JSONB(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column(
            "handicap_strokes_given",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "strokes_given_to_team",
            sa.String(1),
            nullable=False,
            server_default="",
        ),
        sa.Column("result", JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        # Primary Key
        sa.PrimaryKeyConstraint("id", name="pk_matches"),
        # Foreign Keys
        sa.ForeignKeyConstraint(
            ["round_id"],
            ["rounds.id"],
            name="fk_matches_round_id",
            ondelete="CASCADE",
        ),
        # Unique Constraints
        sa.UniqueConstraint(
            "round_id",
            "match_number",
            name="uq_matches_round_match_number",
        ),
        # Check Constraints
        sa.CheckConstraint(
            "match_number >= 1",
            name="ck_matches_match_number_positive",
        ),
    )

    # Indexes for matches
    op.create_index("ix_matches_round_id", "matches", ["round_id"])
    op.create_index("ix_matches_status", "matches", ["status"])

    # =========================================================================
    # 4. New table: team_assignments
    # =========================================================================

    op.create_table(
        "team_assignments",
        sa.Column("id", sa.CHAR(length=36), nullable=False),
        sa.Column("competition_id", sa.CHAR(length=36), nullable=False),
        sa.Column("mode", sa.String(20), nullable=False),
        sa.Column("team_a_player_ids", JSONB(), nullable=False),
        sa.Column("team_b_player_ids", JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        # Primary Key
        sa.PrimaryKeyConstraint("id", name="pk_team_assignments"),
        # Foreign Keys
        sa.ForeignKeyConstraint(
            ["competition_id"],
            ["competitions.id"],
            name="fk_team_assignments_competition_id",
            ondelete="CASCADE",
        ),
    )

    # Indexes for team_assignments
    op.create_index(
        "ix_team_assignments_competition_id",
        "team_assignments",
        ["competition_id"],
    )


def downgrade() -> None:
    # Drop team_assignments
    op.drop_index("ix_team_assignments_competition_id", table_name="team_assignments")
    op.drop_table("team_assignments")

    # Drop matches
    op.drop_index("ix_matches_status", table_name="matches")
    op.drop_index("ix_matches_round_id", table_name="matches")
    op.drop_table("matches")

    # Drop rounds
    op.drop_index("ix_rounds_competition_id_status", table_name="rounds")
    op.drop_index("ix_rounds_status", table_name="rounds")
    op.drop_index("ix_rounds_golf_course_id", table_name="rounds")
    op.drop_index("ix_rounds_competition_id", table_name="rounds")
    op.drop_table("rounds")

    # Revert enrollment fixes
    op.drop_column("enrollments", "tee_category")
