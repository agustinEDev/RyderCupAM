"""refresh_tokens: rotation (replaced_at, replaced_by_id, annulled_at)

F-02 de la auditoría: cada refresco sustituye el refresh token por uno nuevo. El viejo
no se borra: `replaced_at` y `replaced_by_id` distinguen dos pestañas a la vez, una
respuesta perdida y un robo. `annulled_at` marca el sustituto de una respuesta perdida
que se anuló: si alguien vuelve con él, es un robo.

Columnas nulas, sin valor por defecto: en Postgres 11+ no reescriben la tabla y van en
la transacción. Los tokens que ya hay quedan vigentes (NULL) y se rotan en su primer
uso: ninguna sesión cae al desplegar. La release anterior las ignora.

Bajar: la release anterior no distingue un token sustituido de uno vigente y lo
aceptaría (una cookie vieja, quizá robada, volvería a valer). Antes de quitar las
columnas se revocan los sustituidos; los vigentes siguen y nadie pierde la sesión.

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
    op.add_column("refresh_tokens", sa.Column("annulled_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    # Sin esto, la release anterior volvería a aceptar las cookies ya sustituidas
    op.execute(
        "UPDATE refresh_tokens SET revoked = true, revoked_at = now() "
        "WHERE replaced_at IS NOT NULL AND revoked = false"
    )
    op.drop_column("refresh_tokens", "annulled_at")
    op.drop_column("refresh_tokens", "replaced_by_id")
    op.drop_column("refresh_tokens", "replaced_at")
