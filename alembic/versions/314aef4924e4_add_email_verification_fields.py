"""add_email_verification_fields

Revision ID: 314aef4924e4
Revises: 0cfaf48e5b9c
Create Date: 2025-11-12 18:26:22.269066

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '314aef4924e4'
down_revision: Union[str, None] = '0cfaf48e5b9c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Añadir columnas para verificación de email
    op.add_column('users', sa.Column('email_verified', sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column('users', sa.Column('verification_token', sa.String(length=255), nullable=True))
    # Crear índice para búsquedas rápidas por token
    op.create_index('idx_verification_token', 'users', ['verification_token'])


def downgrade() -> None:
    # Eliminar índice y columnas de verificación de email
    op.drop_index('idx_verification_token', table_name='users')
    op.drop_column('users', 'verification_token')
    op.drop_column('users', 'email_verified')
