"""user_devices: when the device's sessions were last closed

Auditoría de la fase 6, B-05: cerrar sesión y cambiar la contraseña revocaban solo los
tokens de refresco, y el de acceso seguía valiendo hasta 15 minutos. Ahora cada
dispositivo guarda cuándo se cerraron sus sesiones, y la API rechaza los accesos
emitidos antes (el token lleva su `iat`). Con zona horaria: se compara con el `iat`,
que es UTC.

Columna nula: en Postgres 11+ no reescribe la tabla. La release anterior sigue
funcionando con la tabla migrada (no la lee).

Revision ID: c2d4e6f8a1b3
Revises: b7e9d1f3a5c8
Create Date: 2026-11-14

"""

import sqlalchemy as sa

from alembic import op

revision = "c2d4e6f8a1b3"
down_revision = "b7e9d1f3a5c8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "user_devices",
        sa.Column("session_closed_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("user_devices", "session_closed_at")
