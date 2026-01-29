"""add is_admin field to users table

Revision ID: 7522c9fc51ef
Revises: c97658d9d49e
Create Date: 2026-01-28 23:33:34.084381

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '7522c9fc51ef'
down_revision: Union[str, None] = 'c97658d9d49e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Añade campo is_admin a la tabla users para Role-Based Access Control (RBAC).

    Campo añadido:
    - is_admin: Flag booleano que indica si el usuario es administrador del sistema

    RBAC Model:
    - ADMIN (Global): is_admin = TRUE - Gestiona campos de golf, aprueba solicitudes
    - CREATOR (Contextual): competition.creator_id == user.id - Gestiona sus competiciones
    - PLAYER (Contextual): enrollment.user_id == user.id AND status = APPROVED - Participa en torneos

    Default: FALSE (todos los usuarios son jugadores por defecto)

    Security: Solo un usuario específico (definido en ADMIN_EMAIL) tendrá is_admin = TRUE
    """
    # Añadir campo is_admin (BOOLEAN, NOT NULL, default FALSE)
    op.add_column(
        "users",
        sa.Column(
            "is_admin",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
            comment="Flag de administrador del sistema (RBAC global)",
        ),
    )

    # Crear índice en is_admin para consultas rápidas
    # Útil para queries: "SELECT * FROM users WHERE is_admin = TRUE"
    # Partial index: solo indexar admins (is_admin = TRUE) para eficiencia
    op.create_index(
        "ix_users_is_admin",
        "users",
        ["is_admin"],
        postgresql_where=sa.text("is_admin = TRUE"),
    )


def downgrade() -> None:
    """
    Elimina el campo is_admin de la tabla users.

    Orden de eliminación:
    1. Eliminar índice
    2. Eliminar columna
    """
    # Eliminar índice primero (dependencia)
    op.drop_index("ix_users_is_admin", table_name="users")

    # Eliminar columna
    op.drop_column("users", "is_admin")
