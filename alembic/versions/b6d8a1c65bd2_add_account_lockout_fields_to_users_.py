"""add account lockout fields to users table

Revision ID: b6d8a1c65bd2
Revises: 3s4721zck3x7
Create Date: 2026-01-07 20:28:46.394592

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "b6d8a1c65bd2"
down_revision: Union[str, None] = "3s4721zck3x7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Añade campos de account lockout a la tabla users.

    Campos añadidos:
    - failed_login_attempts: Contador de intentos fallidos de login (default 0)
    - locked_until: Timestamp hasta cuándo está bloqueada la cuenta (nullable)

    Security Features (OWASP A07):
    - Prevención de ataques de fuerza bruta
    - Bloqueo automático tras 10 intentos fallidos
    - Auto-desbloqueo tras 30 minutos
    - Índice en locked_until para consultas de cuentas bloqueadas
    """
    # Añadir campo failed_login_attempts (INTEGER, NOT NULL, default 0)
    op.add_column(
        "users",
        sa.Column(
            "failed_login_attempts",
            sa.Integer(),
            nullable=False,
            server_default="0",
            comment="Contador de intentos fallidos de login (resetea en login exitoso)",
        ),
    )

    # Añadir campo locked_until (TIMESTAMP, nullable)
    op.add_column(
        "users",
        sa.Column(
            "locked_until",
            sa.DateTime(),
            nullable=True,
            comment="Timestamp hasta cuándo está bloqueada la cuenta (NULL = no bloqueada)",
        ),
    )

    # Índice en locked_until para consultas de cuentas bloqueadas
    # Útil para queries: "¿Cuántas cuentas están bloqueadas ahora?"
    # Solo indexar cuentas con bloqueo activo (locked_until IS NOT NULL)
    op.create_index(
        "ix_users_locked_until",
        "users",
        ["locked_until"],
        postgresql_where=sa.text("locked_until IS NOT NULL"),
    )


def downgrade() -> None:
    """
    Elimina los campos de account lockout de la tabla users.

    Orden de eliminación:
    1. Eliminar índice
    2. Eliminar columnas
    """
    # Eliminar índice primero (dependencia)
    op.drop_index("ix_users_locked_until", table_name="users")

    # Eliminar columnas
    op.drop_column("users", "locked_until")
    op.drop_column("users", "failed_login_attempts")
