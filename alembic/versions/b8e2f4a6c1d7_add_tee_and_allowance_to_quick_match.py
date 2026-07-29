"""Add tee selection to quick_match participants and allowance_percentage

Revision ID: b8e2f4a6c1d7
Revises: a3f7c1d9e2b4
Create Date: 2026-07-28 00:20:00.000000

"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "b8e2f4a6c1d7"
down_revision = "a3f7c1d9e2b4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "quick_matches",
        sa.Column("allowance_percentage", sa.Integer(), nullable=True),
    )
    # tee_category/tee_gender per participant live inside the existing
    # `participants` JSONB column (QuickMatchParticipantsJsonType) — no
    # schema change needed for those, existing rows simply have them null.


def downgrade() -> None:
    op.drop_column("quick_matches", "allowance_percentage")
