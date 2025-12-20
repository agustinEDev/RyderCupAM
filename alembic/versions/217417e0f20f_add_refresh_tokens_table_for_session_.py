"""add refresh_tokens table for session management

Revision ID: 217417e0f20f
Revises: c283e057a219
Create Date: 2025-12-16 16:49:39.645366

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '217417e0f20f'
down_revision: Union[str, None] = 'c283e057a219'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Crea la tabla refresh_tokens para Session Timeout (v1.8.0).

    Esta tabla almacena refresh tokens para permitir renovación de access tokens
    sin re-autenticación, mejorando la seguridad al:
    - Reducir duración de access tokens (60 min → 15 min)
    - Permitir revocación de sesiones en logout
    - Rastrear sesiones activas por usuario
    """
    op.create_table(
        'refresh_tokens',
        # ID del refresh token (UUID)
        sa.Column('id', sa.String(length=36), nullable=False, primary_key=True),

        # Foreign key a users.id
        sa.Column('user_id', sa.String(length=36), nullable=False),

        # Hash SHA256 del token JWT (64 caracteres hex)
        # No almacenamos el token en texto plano por seguridad
        sa.Column('token_hash', sa.String(length=64), nullable=False, unique=True),

        # Fecha de expiración del refresh token (7 días por defecto)
        sa.Column('expires_at', sa.DateTime(), nullable=False),

        # Fecha de creación del token
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),

        # Si el token ha sido revocado manualmente (logout, cambio de contraseña)
        sa.Column('revoked', sa.Boolean(), nullable=False, server_default='false'),

        # Fecha de revocación (NULL si no ha sido revocado)
        sa.Column('revoked_at', sa.DateTime(), nullable=True),
    )

    # Índice en user_id para queries rápidas de "tokens por usuario"
    op.create_index(
        'ix_refresh_tokens_user_id',
        'refresh_tokens',
        ['user_id']
    )

    # Índice único en token_hash para búsquedas rápidas y prevenir duplicados
    op.create_index(
        'ix_refresh_tokens_token_hash',
        'refresh_tokens',
        ['token_hash'],
        unique=True
    )

    # Índice en expires_at para limpieza eficiente de tokens expirados
    op.create_index(
        'ix_refresh_tokens_expires_at',
        'refresh_tokens',
        ['expires_at']
    )

    # Foreign key constraint a tabla users
    op.create_foreign_key(
        'fk_refresh_tokens_user_id',
        'refresh_tokens',
        'users',
        ['user_id'],
        ['id'],
        ondelete='CASCADE'  # Si se elimina el usuario, eliminar sus refresh tokens
    )


def downgrade() -> None:
    """Elimina la tabla refresh_tokens."""
    op.drop_table('refresh_tokens')
