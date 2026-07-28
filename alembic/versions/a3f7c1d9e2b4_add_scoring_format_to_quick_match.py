"""Add scoring_format to quick_match, make match_format nullable

Revision ID: a3f7c1d9e2b4
Revises: de76ad1f8cf2
Create Date: 2026-07-27 22:00:00.000000

"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "a3f7c1d9e2b4"
down_revision = "de76ad1f8cf2"
branch_labels = None
depends_on = None

CHECK_CONSTRAINT_NAME = "ck_quick_matches_exactly_one_format"


def upgrade() -> None:
    op.add_column(
        "quick_matches",
        sa.Column("scoring_format", sa.String(length=20), nullable=True),
    )
    op.alter_column("quick_matches", "match_format", existing_type=sa.String(length=20), nullable=True)
    op.create_check_constraint(
        CHECK_CONSTRAINT_NAME,
        "quick_matches",
        "(match_format IS NULL) <> (scoring_format IS NULL)",
    )


def downgrade() -> None:
    # Free-play matches (scoring_format set) carry rosters up to 4 players and no
    # teams, incompatible with the pre-existing match_format-only schema (SINGLES
    # is 1v1, capacity 2). Rewriting them to SINGLES would silently corrupt their
    # roster/scoring semantics, so refuse the downgrade instead.
    connection = op.get_bind()
    remaining = connection.execute(
        sa.text("SELECT COUNT(*) FROM quick_matches WHERE scoring_format IS NOT NULL")
    ).scalar()
    if remaining:
        raise RuntimeError(
            f"Cannot downgrade: {remaining} quick_matches row(s) have scoring_format set "
            "(free-play matches). Archive or manually migrate those rows before retrying."
        )

    op.drop_constraint(CHECK_CONSTRAINT_NAME, "quick_matches", type_="check")
    op.alter_column("quick_matches", "match_format", existing_type=sa.String(length=20), nullable=False)
    op.drop_column("quick_matches", "scoring_format")
