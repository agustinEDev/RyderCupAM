"""create_competition_module_tables

Revision ID: 7610ccc63d69
Revises: 852ad2e01efe
Create Date: 2025-11-18 14:17:26.818262

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# Import seed functions
import sys
from pathlib import Path

# Add alembic/seeds to Python path
seeds_path = Path(__file__).parent.parent / "seeds"
sys.path.insert(0, str(seeds_path))

from seed_countries import seed_countries, seed_country_adjacencies


# revision identifiers, used by Alembic.
revision: str = '7610ccc63d69'
down_revision: Union[str, None] = '852ad2e01efe'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Crear tabla countries (shared domain)
    op.create_table(
        'countries',
        sa.Column('code', sa.String(length=2), nullable=False),
        sa.Column('active', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('name_en', sa.String(length=100), nullable=False),
        sa.Column('name_es', sa.String(length=100), nullable=False),
        sa.PrimaryKeyConstraint('code')
    )

    # 2. Crear tabla country_adjacencies (relación muchos-a-muchos)
    op.create_table(
        'country_adjacencies',
        sa.Column('country_code_1', sa.String(length=2), nullable=False),
        sa.Column('country_code_2', sa.String(length=2), nullable=False),
        sa.ForeignKeyConstraint(['country_code_1'], ['countries.code'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['country_code_2'], ['countries.code'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('country_code_1', 'country_code_2')
    )

    # 3. Crear tabla competitions
    op.create_table(
        'competitions',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('creator_id', sa.String(length=36), nullable=False),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('start_date', sa.Date(), nullable=False),
        sa.Column('end_date', sa.Date(), nullable=False),
        sa.Column('country_code', sa.String(length=2), nullable=False),
        sa.Column('secondary_country_code', sa.String(length=2), nullable=True),
        sa.Column('team_1_name', sa.String(length=100), nullable=False),
        sa.Column('team_2_name', sa.String(length=100), nullable=False),
        sa.Column('handicap_type', sa.String(length=20), nullable=False),
        sa.Column('handicap_value', sa.Integer(), nullable=False),
        sa.Column('max_players', sa.Integer(), nullable=False, server_default=sa.text('24')),
        sa.Column('team_assignment', sa.String(length=20), nullable=False, server_default=sa.text("'MANUAL'")),
        sa.Column('status', sa.String(length=20), nullable=False, server_default=sa.text("'DRAFT'")),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['creator_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['country_code'], ['countries.code'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['secondary_country_code'], ['countries.code'], ondelete='RESTRICT')
    )

    # Crear índices para competitions
    op.create_index('ix_competitions_creator_id', 'competitions', ['creator_id'])
    op.create_index('ix_competitions_status', 'competitions', ['status'])
    op.create_index('ix_competitions_start_date', 'competitions', ['start_date'])

    # 4. Crear tabla enrollments
    op.create_table(
        'enrollments',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('competition_id', sa.String(length=36), nullable=False),
        sa.Column('user_id', sa.String(length=36), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('team_id', sa.String(length=10), nullable=True),
        sa.Column('custom_handicap', sa.Numeric(precision=4, scale=1), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['competition_id'], ['competitions.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.UniqueConstraint('competition_id', 'user_id', name='uq_enrollment_competition_user')
    )

    # Crear índices para enrollments
    op.create_index('ix_enrollments_competition_id', 'enrollments', ['competition_id'])
    op.create_index('ix_enrollments_user_id', 'enrollments', ['user_id'])
    op.create_index('ix_enrollments_status', 'enrollments', ['status'])

    # 5. Seed data: Insertar países y adyacencias
    seed_countries()
    seed_country_adjacencies()


def downgrade() -> None:
    # Eliminar en orden inverso (por dependencias)
    op.drop_index('ix_enrollments_status', table_name='enrollments')
    op.drop_index('ix_enrollments_user_id', table_name='enrollments')
    op.drop_index('ix_enrollments_competition_id', table_name='enrollments')
    op.drop_table('enrollments')

    op.drop_index('ix_competitions_start_date', table_name='competitions')
    op.drop_index('ix_competitions_status', table_name='competitions')
    op.drop_index('ix_competitions_creator_id', table_name='competitions')
    op.drop_table('competitions')

    op.drop_table('country_adjacencies')
    op.drop_table('countries')
