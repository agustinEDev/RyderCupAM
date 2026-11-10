"""refresh_tokens: rotation (replaced_at, replaced_by_id)

F-02 de la auditoría: cada refresco sustituye el refresh token por uno nuevo. El viejo
no se borra: `replaced_at` y `replaced_by_id` distinguen dos pestañas a la vez, una
respuesta perdida y un robo.

Columnas nulas, sin valor por defecto: en Postgres 11+ no reescriben la tabla y van en
la transacción. Los tokens que ya hay quedan vigentes (NULL) y se rotan en su primer
uso: ninguna sesión cae al desplegar. La release anterior las ignora.

Revision ID: b3d5f7a9c1e2
Revises: a2c4e6f8b0d1
Create Date: 2026-11-10

"""

import sqlalchemy as sa
from alembic import op

revision = "b3d5f7a9c1e2"
down_revision = "a2c4e6f8b0d1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("refresh_tokens", sa.Column("replaced_at", sa.DateTime(), nullable=True))
    op.add_column(
        "refresh_tokens", sa.Column("replaced_by_id", sa.String(length=36), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("refresh_tokens", "replaced_by_id")
    op.drop_column("refresh_tokens", "replaced_at")
