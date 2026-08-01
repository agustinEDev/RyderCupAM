"""add is_active field to users table

Revision ID: f3a9c2e7b1d4
Revises: 5e13a3225101
Create Date: 2026-08-02 10:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'f3a9c2e7b1d4'
down_revision: str | None = '5e13a3225101'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """
    Añade campo is_active a la tabla users para el panel de administración.

    Campo añadido:
    - is_active: Flag booleano que indica si la cuenta está activa. Un admin
      puede desactivar una cuenta (bloquea login, conserva todos los datos)
      desde el panel de administración.

    Default: TRUE (todos los usuarios existentes quedan activos).
    """
    op.add_column(
        "users",
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
            comment="Cuenta activa (FALSE si un admin la desactivó desde el panel)",
        ),
    )

    # Partial index: solo indexar cuentas desactivadas (caso poco frecuente)
    # para acelerar el listado "usuarios desactivados" en el panel de admin.
    op.create_index(
        "ix_users_is_active_false",
        "users",
        ["is_active"],
        postgresql_where=sa.text("is_active = FALSE"),
    )


def downgrade() -> None:
    """Elimina el campo is_active de la tabla users."""
    op.drop_index("ix_users_is_active_false", table_name="users")
    op.drop_column("users", "is_active")
