"""make_handicap_value_nullable

Revision ID: b4301dc0075c
Revises: f67961867576
Create Date: 2025-11-19 01:09:22.575732

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b4301dc0075c'
down_revision: Union[str, None] = 'f67961867576'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Cambiar handicap_value a nullable=True
    # Esto es necesario porque los torneos SCRATCH no tienen porcentaje de hándicap
    op.alter_column(
        'competitions',
        'handicap_value',
        existing_type=sa.Integer(),
        nullable=True
    )


def downgrade() -> None:
    # Revertir a nullable=False
    # Nota: Esto fallará si hay valores NULL en la columna
    op.alter_column(
        'competitions',
        'handicap_value',
        existing_type=sa.Integer(),
        nullable=False
    )
