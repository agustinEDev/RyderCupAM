"""make_handicap_updated_at_timezone_aware

Revision ID: 117fa75bd4ee
Revises: 2acbed9e2365
Create Date: 2026-07-04 00:54:12.443720

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '117fa75bd4ee'
down_revision: Union[str, None] = '2acbed9e2365'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Existing values were written with naive datetime.now() on a server that
    # runs in UTC, so they are reinterpreted as UTC rather than converted.
    op.execute(
        "ALTER TABLE users "
        "ALTER COLUMN handicap_updated_at "
        "TYPE TIMESTAMP WITH TIME ZONE "
        "USING handicap_updated_at AT TIME ZONE 'UTC'"
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE users "
        "ALTER COLUMN handicap_updated_at "
        "TYPE TIMESTAMP WITHOUT TIME ZONE "
        "USING handicap_updated_at AT TIME ZONE 'UTC'"
    )
