"""add_device_id_to_refresh_tokens

Revision ID: c97658d9d49e
Revises: 50ccf425ff32
Create Date: 2026-01-12 09:54:02.032684

PROPÓSITO:
Vincular refresh_tokens con user_devices para permitir revocación correcta
de sesiones cuando se revoca un dispositivo.

PROBLEMA QUE RESUELVE:
- Sin device_id: revocar un dispositivo NO cerraba sus sesiones activas
- Los refresh_tokens permanecían válidos → usuario seguía logueado
- No había forma de saber qué tokens pertenecían a qué dispositivo

SOLUCIÓN:
- Agregar columna device_id (FK a user_devices.id)
- Permite invalidar TODOS los refresh_tokens de un dispositivo
- Al revocar dispositivo → se invalidan sus tokens → sesión se cierra

COMPORTAMIENTO:
- device_id es NULLABLE para compatibilidad con tokens antiguos
- Nuevos tokens SIEMPRE tendrán device_id asociado
- Tokens legacy (device_id=NULL) se revocarán en próximo login
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'c97658d9d49e'
down_revision: str | None = '50ccf425ff32'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """
    Agrega columna device_id a refresh_tokens.

    NOTA: La columna es NULLABLE para permitir:
    1. Migración sin romper tokens existentes
    2. Backward compatibility temporal
    3. Cleanup gradual de tokens legacy
    """
    # Agregar columna device_id (nullable)
    op.add_column(
        'refresh_tokens',
        sa.Column('device_id', sa.String(length=36), nullable=True)
    )

    # Crear foreign key a user_devices.id
    op.create_foreign_key(
        'fk_refresh_tokens_device_id',
        'refresh_tokens',
        'user_devices',
        ['device_id'],
        ['id'],
        ondelete='CASCADE'  # Si se borra dispositivo, se borran sus tokens
    )

    # Crear índice para búsquedas por device_id (performance)
    op.create_index(
        'ix_refresh_tokens_device_id',
        'refresh_tokens',
        ['device_id']
    )


def downgrade() -> None:
    """
    Revierte la migración eliminando device_id.

    ADVERTENCIA: Esto romperá la funcionalidad de revocación por dispositivo.
    """
    # Eliminar índice
    op.drop_index('ix_refresh_tokens_device_id', table_name='refresh_tokens')

    # Eliminar foreign key
    op.drop_constraint('fk_refresh_tokens_device_id', 'refresh_tokens', type_='foreignkey')

    # Eliminar columna
    op.drop_column('refresh_tokens', 'device_id')
