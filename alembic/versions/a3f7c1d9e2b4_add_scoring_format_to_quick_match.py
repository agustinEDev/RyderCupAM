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


def upgrade() -> None:
    op.add_column(
        "quick_matches",
        sa.Column("scoring_format", sa.String(length=20), nullable=True),
    )
    op.alter_column("quick_matches", "match_format", existing_type=sa.String(length=20), nullable=True)


def downgrade() -> None:
    op.execute("UPDATE quick_matches SET match_format = 'SINGLES' WHERE match_format IS NULL")
    op.alter_column("quick_matches", "match_format", existing_type=sa.String(length=20), nullable=False)
    op.drop_column("quick_matches", "scoring_format")
