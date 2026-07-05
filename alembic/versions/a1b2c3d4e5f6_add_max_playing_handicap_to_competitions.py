"""Add max_playing_handicap to competitions table

Revision ID: a1b2c3d4e5f6
Revises: f6b8c4d2e3a5
Create Date: 2026-07-01 14:00:00.000000

"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "a1b2c3d4e5f6"
down_revision = "f6b8c4d2e3a5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "competitions",
        sa.Column("max_playing_handicap", sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("competitions", "max_playing_handicap")
