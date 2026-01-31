"""create_golf_course_tables

Revision ID: af107e8f82c6
Revises: 7522c9fc51ef
Create Date: 2026-01-30 19:13:51.994226

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'af107e8f82c6'
down_revision: Union[str, None] = '7522c9fc51ef'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create golf_courses table (ENUMs will be created automatically by SQLAlchemy)
    op.create_table(
        'golf_courses',
        sa.Column('id', sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(length=200), nullable=False, comment='Nombre del campo de golf'),
        sa.Column('country_code', sa.String(length=2), nullable=False),
        sa.Column('course_type', sa.Enum('STANDARD_18', 'PITCH_AND_PUTT', 'EXECUTIVE', name='course_type_enum'), nullable=False, comment='Tipo de campo (STANDARD_18, etc.)'),
        sa.Column('creator_id', sa.CHAR(length=36), nullable=False),
        sa.Column('approval_status', sa.Enum('PENDING_APPROVAL', 'APPROVED', 'REJECTED', name='approval_status_enum'), nullable=False, server_default='PENDING_APPROVAL', comment='Estado de aprobación (PENDING_APPROVAL, APPROVED, REJECTED)'),
        sa.Column('rejection_reason', sa.String(length=500), nullable=True, comment='Razón de rechazo (solo si REJECTED)'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.CheckConstraint("LENGTH(name) >= 3", name='ck_golf_courses_name_min_length'),
        sa.CheckConstraint("(approval_status != 'REJECTED') OR (rejection_reason IS NOT NULL)", name='ck_golf_courses_rejection_reason_required'),
        sa.ForeignKeyConstraint(['country_code'], ['countries.code'], ),
        sa.ForeignKeyConstraint(['creator_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
        comment='Campos de golf con workflow de aprobación Admin'
    )

    # Create golf_course_tees table
    op.create_table(
        'golf_course_tees',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('golf_course_id', sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('tee_category', sa.Enum('CHAMPIONSHIP_MALE', 'CHAMPIONSHIP_FEMALE', 'AMATEUR_MALE', 'AMATEUR_FEMALE', 'SENIOR_MALE', 'SENIOR_FEMALE', 'JUNIOR', name='tee_category_enum'), nullable=False, comment='Categoría normalizada WHS (CHAMPIONSHIP_MALE, etc.)'),
        sa.Column('identifier', sa.String(length=50), nullable=False, comment='Identificador libre del campo (Amarillo, Oro, 1, etc.)'),
        sa.Column('course_rating', sa.Float(), nullable=False, comment='Course Rating WHS (50.0-90.0)'),
        sa.Column('slope_rating', sa.Integer(), nullable=False, comment='Slope Rating WHS (55-155)'),
        sa.CheckConstraint('course_rating >= 50.0 AND course_rating <= 90.0', name='ck_tees_course_rating_range'),
        sa.CheckConstraint('slope_rating >= 55 AND slope_rating <= 155', name='ck_tees_slope_rating_range'),
        sa.ForeignKeyConstraint(['golf_course_id'], ['golf_courses.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('golf_course_id', 'tee_category', name='uq_golf_course_tees_category'),
        comment='Tees (salidas) de campos de golf con ratings WHS'
    )

    # Create golf_course_holes table
    op.create_table(
        'golf_course_holes',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('golf_course_id', sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('hole_number', sa.Integer(), nullable=False, comment='Número de hoyo (1-18)'),
        sa.Column('par', sa.Integer(), nullable=False, comment='Par del hoyo (3-5)'),
        sa.Column('stroke_index', sa.Integer(), nullable=False, comment='Índice de dificultad (1-18)'),
        sa.CheckConstraint('hole_number >= 1 AND hole_number <= 18', name='ck_holes_number_range'),
        sa.CheckConstraint('par >= 3 AND par <= 5', name='ck_holes_par_range'),
        sa.CheckConstraint('stroke_index >= 1 AND stroke_index <= 18', name='ck_holes_stroke_index_range'),
        sa.ForeignKeyConstraint(['golf_course_id'], ['golf_courses.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('golf_course_id', 'hole_number', name='uq_golf_course_holes_number'),
        sa.UniqueConstraint('golf_course_id', 'stroke_index', name='uq_golf_course_holes_stroke_index'),
        comment='Hoyos de campos de golf con par y stroke index'
    )

    # Create indexes
    op.create_index('ix_golf_courses_approval_status', 'golf_courses', ['approval_status'])
    op.create_index('ix_golf_courses_creator_id', 'golf_courses', ['creator_id'])
    op.create_index('ix_golf_courses_country_code', 'golf_courses', ['country_code'])


def downgrade() -> None:
    # Drop indexes
    op.drop_index('ix_golf_courses_country_code', table_name='golf_courses')
    op.drop_index('ix_golf_courses_creator_id', table_name='golf_courses')
    op.drop_index('ix_golf_courses_approval_status', table_name='golf_courses')

    # Drop tables
    op.drop_table('golf_course_holes')
    op.drop_table('golf_course_tees')
    op.drop_table('golf_courses')

    # Drop ENUM types
    op.execute('DROP TYPE tee_category_enum')
    op.execute('DROP TYPE approval_status_enum')
    op.execute('DROP TYPE course_type_enum')
