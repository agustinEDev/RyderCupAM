"""rename handicap_type to play_mode and drop handicap_value

Revision ID: b9e4f1a3c7d2
Revises: a7f3b2c8d4e1
Create Date: 2026-02-05 21:00:00.000000

Sprint 2 - Replaces Competition HandicapSettings(SCRATCH/PERCENTAGE, 90/95/100)
with PlayMode(SCRATCH/HANDICAP). Allowance percentages now configured per Round.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "b9e4f1a3c7d2"
down_revision: Union[str, None] = "a7f3b2c8d4e1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Rename column handicap_type -> play_mode
    op.alter_column(
        "competitions",
        "handicap_type",
        new_column_name="play_mode",
    )

    # 2. Convert values: PERCENTAGE -> HANDICAP
    op.execute("UPDATE competitions SET play_mode = 'HANDICAP' WHERE play_mode = 'PERCENTAGE'")

    # 3. Drop handicap_value column (no longer needed)
    op.drop_column("competitions", "handicap_value")


def downgrade() -> None:
    # 1. Add handicap_value column back
    op.add_column(
        "competitions",
        sa.Column("handicap_value", sa.Integer(), nullable=True),
    )

    # 2. Rename column play_mode -> handicap_type
    op.alter_column(
        "competitions",
        "play_mode",
        new_column_name="handicap_type",
    )

    # 3. Convert values back: HANDICAP -> PERCENTAGE
    op.execute(
        "UPDATE competitions SET handicap_type = 'PERCENTAGE' WHERE handicap_type = 'HANDICAP'"
    )
