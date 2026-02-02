"""add competition_golf_courses association table

Revision ID: 2b72b9741fd1
Revises: c5f8a3b2d1e9
Create Date: 2026-01-31 21:05:41.086394

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2b72b9741fd1'
down_revision: Union[str, None] = 'c5f8a3b2d1e9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Importar UUID de postgresql para golf_course_id (UUID nativo)
    from sqlalchemy.dialects.postgresql import UUID

    # Crear tabla de asociación competition_golf_courses
    # IMPORTANTE: competition_id usa CHAR(36) para coincidir con competitions.id
    # golf_course_id usa UUID(as_uuid=True) para coincidir con golf_courses.id
    op.create_table(
        'competition_golf_courses',
        sa.Column('id', sa.CHAR(length=36), nullable=False),
        sa.Column('competition_id', sa.CHAR(length=36), nullable=False),
        sa.Column('golf_course_id', UUID(as_uuid=True), nullable=False),
        sa.Column('display_order', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),

        # Primary Key
        sa.PrimaryKeyConstraint('id', name='pk_competition_golf_courses'),

        # Foreign Keys
        sa.ForeignKeyConstraint(
            ['competition_id'], ['competitions.id'],
            name='fk_competition_golf_courses_competition_id',
            ondelete='CASCADE'
        ),
        sa.ForeignKeyConstraint(
            ['golf_course_id'], ['golf_courses.id'],
            name='fk_competition_golf_courses_golf_course_id',
            ondelete='CASCADE'
        ),

        # Unique Constraints
        sa.UniqueConstraint(
            'competition_id', 'golf_course_id',
            name='uq_competition_golf_courses_competition_golf_course'
        ),
        sa.UniqueConstraint(
            'competition_id', 'display_order',
            name='uq_competition_golf_courses_competition_display_order'
        ),

        # Check Constraint
        sa.CheckConstraint(
            'display_order >= 1',
            name='ck_competition_golf_courses_display_order_positive'
        )
    )

    # Índices para optimizar búsquedas
    op.create_index(
        'ix_competition_golf_courses_competition_id',
        'competition_golf_courses',
        ['competition_id']
    )
    op.create_index(
        'ix_competition_golf_courses_golf_course_id',
        'competition_golf_courses',
        ['golf_course_id']
    )


def downgrade() -> None:
    # Eliminar índices
    op.drop_index('ix_competition_golf_courses_golf_course_id', table_name='competition_golf_courses')
    op.drop_index('ix_competition_golf_courses_competition_id', table_name='competition_golf_courses')

    # Eliminar tabla
    op.drop_table('competition_golf_courses')
