"""remove par from golf_course_tees

Revision ID: c5f8a3b2d1e9
Revises: bad5e4052f9f
Create Date: 2026-01-31 16:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c5f8a3b2d1e9'
down_revision: Union[str, None] = 'bad5e4052f9f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Remove 'par' column from golf_course_tees table.

    This column was incorrectly added in the initial migration.
    Par belongs only to golf_course_holes, not to tees.

    CodeRabbit Issue #1 fix.
    """
    # Check if column exists before dropping (idempotent)
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    columns = [col['name'] for col in inspector.get_columns('golf_course_tees')]

    if 'par' in columns:
        op.drop_column('golf_course_tees', 'par')


def downgrade() -> None:
    """
    Re-add 'par' column to golf_course_tees (for rollback only).

    Note: This is not recommended as par doesn't belong in tees.
    """
    op.add_column(
        'golf_course_tees',
        sa.Column('par', sa.INTEGER(), nullable=False, server_default='72')
    )
