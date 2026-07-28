"""Add name to quick_match

Revision ID: de76ad1f8cf2
Revises: 9a9440cebb07
Create Date: 2026-07-27 18:00:00.000000

"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "de76ad1f8cf2"
down_revision = "9a9440cebb07"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "quick_matches",
        sa.Column("name", sa.String(length=100), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("quick_matches", "name")
