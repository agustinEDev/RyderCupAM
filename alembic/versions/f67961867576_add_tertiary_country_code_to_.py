"""add_tertiary_country_code_to_competitions

Revision ID: f67961867576
Revises: 7610ccc63d69
Create Date: 2025-11-18 14:55:51.171643

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f67961867576'
down_revision: Union[str, None] = '7610ccc63d69'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Agregar columna tertiary_country_code para soportar torneos en hasta 3 países
    op.add_column(
        'competitions',
        sa.Column('tertiary_country_code', sa.String(length=2), nullable=True)
    )

    # Agregar foreign key a countries
    op.create_foreign_key(
        'competitions_tertiary_country_code_fkey',
        'competitions',
        'countries',
        ['tertiary_country_code'],
        ['code'],
        ondelete='RESTRICT'
    )


def downgrade() -> None:
    # Eliminar foreign key
    op.drop_constraint(
        'competitions_tertiary_country_code_fkey',
        'competitions',
        type_='foreignkey'
    )

    # Eliminar columna
    op.drop_column('competitions', 'tertiary_country_code')
