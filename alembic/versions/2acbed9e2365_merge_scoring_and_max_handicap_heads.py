"""merge scoring and max handicap heads

Revision ID: 2acbed9e2365
Revises: a1b2c3d4e5f6, a3d5e7f1b2c4
Create Date: 2026-07-01 21:09:32.472668

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2acbed9e2365'
down_revision: Union[str, None] = ('a1b2c3d4e5f6', 'a3d5e7f1b2c4')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
