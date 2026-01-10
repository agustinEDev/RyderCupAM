"""add password reset fields to users table

Revision ID: 3s4721zck3x7
Revises: 217417e0f20f
Create Date: 2025-12-26 12:09:09.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "3s4721zck3x7"
down_revision: Union[str, None] = "217417e0f20f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Añade campos de password reset a la tabla users.

    Campos añadidos:
    - password_reset_token: Token seguro para resetear contraseña (nullable)
    - reset_token_expires_at: Timestamp de expiración del token (nullable)

    Security Features (OWASP A07):
    - Token de 256 bits criptográficamente seguro (secrets.token_urlsafe)
    - Expiración automática en 24 horas
    - Token de un solo uso (se invalida después del primer uso exitoso)
    - Índice en password_reset_token para búsquedas rápidas
    """
    # Añadir campo password_reset_token (VARCHAR 255, nullable)
    op.add_column(
        "users",
        sa.Column(
            "password_reset_token",
            sa.String(length=255),
            nullable=True,
            comment="Token de reseteo de contraseña (válido 24h, uso único)",
        ),
    )

    # Añadir campo reset_token_expires_at (TIMESTAMP, nullable)
    op.add_column(
        "users",
        sa.Column(
            "reset_token_expires_at",
            sa.DateTime(),
            nullable=True,
            comment="Fecha de expiración del token de reseteo (24h desde generación)",
        ),
    )

    # Índice único en password_reset_token para búsquedas rápidas
    # Solo tokens activos pueden estar indexados (nullable permite múltiples NULL)
    op.create_index(
        "ix_users_password_reset_token",
        "users",
        ["password_reset_token"],
        unique=True,
        postgresql_where=sa.text("password_reset_token IS NOT NULL"),
    )

    # Índice en reset_token_expires_at para limpieza eficiente de tokens expirados
    # Útil para tareas de mantenimiento que eliminen tokens vencidos
    op.create_index(
        "ix_users_reset_token_expires_at",
        "users",
        ["reset_token_expires_at"],
        postgresql_where=sa.text("reset_token_expires_at IS NOT NULL"),
    )


def downgrade() -> None:
    """
    Elimina los campos de password reset de la tabla users.

    Orden de eliminación:
    1. Eliminar índices
    2. Eliminar columnas
    """
    # Eliminar índices primero (dependencias)
    op.drop_index("ix_users_reset_token_expires_at", table_name="users")
    op.drop_index("ix_users_password_reset_token", table_name="users")

    # Eliminar columnas
    op.drop_column("users", "reset_token_expires_at")
    op.drop_column("users", "password_reset_token")
