"""add password_history table

Revision ID: d850bb7f327d
Revises: b6d8a1c65bd2
Create Date: 2026-01-08 13:14:15.355833

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'd850bb7f327d'
down_revision: Union[str, None] = 'b6d8a1c65bd2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Crea la tabla password_history para prevenir reutilización de contraseñas.

    Security Features (OWASP A07):
    - Previene reutilización de últimas 5 contraseñas
    - Hashes almacenados con bcrypt (no texto plano)
    - Limpieza automática de registros > 1 año
    - Índices optimizados para consultas frecuentes
    """
    # Crear tabla password_history
    op.create_table(
        'password_history',
        sa.Column('id', sa.CHAR(length=36), nullable=False),
        sa.Column('user_id', sa.CHAR(length=36), nullable=False),
        sa.Column('password_hash', sa.String(length=255), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        comment='Historial de contraseñas para prevenir reutilización (últimas 5, máx 1 año)'
    )

    # Índice compuesto: user_id + created_at DESC
    # Optimiza consulta frecuente: "Obtener últimas 5 contraseñas de un usuario"
    op.create_index(
        'ix_password_history_user_created',
        'password_history',
        ['user_id', sa.text('created_at DESC')],
        unique=False
    )

    # Índice en created_at para limpieza automática
    # Optimiza query: "Eliminar registros > 1 año"
    op.create_index(
        'ix_password_history_created_at',
        'password_history',
        ['created_at'],
        unique=False
    )


def downgrade() -> None:
    """
    Elimina la tabla password_history y sus índices.

    Orden de eliminación:
    1. Índices
    2. Tabla (la FK se elimina automáticamente con la tabla)
    """
    # Eliminar índices
    op.drop_index('ix_password_history_created_at', table_name='password_history')
    op.drop_index('ix_password_history_user_created', table_name='password_history')

    # Eliminar tabla
    op.drop_table('password_history')
