"""remove par from golf_course_tees

Revision ID: c5f8a3b2d1e9
Revises: bad5e4052f9f
Create Date: 2026-01-31 16:30:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'c5f8a3b2d1e9'
down_revision: str | None = 'bad5e4052f9f'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """
    Remove 'par' column from golf_course_tees table.

    This column was incorrectly added in the initial migration.
    Par belongs only to golf_course_holes, not to tees.

    CodeRabbit Issue #1 fix.

    Uses PostgreSQL's DROP COLUMN IF EXISTS for idempotency.
    Compatible with both online and offline (--sql) modes.
    """
    # Use raw SQL to support both online and offline modes
    # PostgreSQL's IF EXISTS makes this idempotent
    op.execute('ALTER TABLE golf_course_tees DROP COLUMN IF EXISTS par')


def downgrade() -> None:
    """
    Re-add 'par' column to golf_course_tees (for rollback only).

    Note: This is not recommended as par doesn't belong in tees.
    """
    op.add_column(
        'golf_course_tees',
        sa.Column('par', sa.INTEGER(), nullable=False, server_default='72')
    )
