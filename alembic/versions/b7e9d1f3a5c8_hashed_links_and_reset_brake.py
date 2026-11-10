"""users: email links stored hashed, with expiry; sign-up notice and reset email quota

Fase 3 (F-04/F-05/F-10/F-13, F-01):
- Los enlaces de verificar y de restablecer se guardan con el SHA-256 del token. Los
  pendientes en claro dejan de valer al desplegar (decidido por Agustín): se borran
  aquí, y quien pulse uno viejo ve «enlace no válido». Los que ya son un hash (64
  caracteres hexadecimales) se dejan.
- `verification_token_expires_at`: la verificación caduca a las 48 h.
- `register_attempt_notice_at`: el último aviso al dueño de un intento de registro con su
  correo (uno al día).
- `password_reset_emails_in_window` y `password_reset_window_started_at`: el cupo de 10
  correos de restablecer por cuenta en 24 h.

Despliegue escalonado (ADR-048, B-3): mientras la 2.56 sigue sirviendo junto a la 2.57,
puede escribir un enlace en claro después de esta migración. La migración de la 2.58.0
repite los dos UPDATE de abajo (`docs/pendientes-de-release.md`).

Columnas nulas o con valor por defecto constante: en Postgres 11+ no reescriben la
tabla. La release anterior sigue funcionando con la tabla migrada (no lee las nuevas).

Revision ID: b7e9d1f3a5c8
Revises: a2c4e6f8b0d1
Create Date: 2026-11-10

"""

import sqlalchemy as sa

from alembic import op

revision = "b7e9d1f3a5c8"
down_revision = "a2c4e6f8b0d1"
branch_labels = None
depends_on = None

# Un SHA-256 en hexadecimal, como lo escribe el código nuevo
_ES_UN_HASH = "'^[0-9a-f]{64}$'"


def upgrade() -> None:
    op.add_column("users", sa.Column("verification_token_expires_at", sa.DateTime(), nullable=True))
    op.add_column("users", sa.Column("register_attempt_notice_at", sa.DateTime(), nullable=True))
    op.add_column(
        "users",
        sa.Column(
            "password_reset_emails_in_window",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )
    op.add_column(
        "users", sa.Column("password_reset_window_started_at", sa.DateTime(), nullable=True)
    )
    # Los enlaces en claro, fuera: ni se pueden encontrar ya ni deben quedar en la BD
    op.execute(
        "UPDATE users SET verification_token = NULL "
        f"WHERE verification_token IS NOT NULL AND verification_token !~ {_ES_UN_HASH}"
    )
    op.execute(
        "UPDATE users SET password_reset_token = NULL, reset_token_expires_at = NULL "
        f"WHERE password_reset_token IS NOT NULL AND password_reset_token !~ {_ES_UN_HASH}"
    )


def downgrade() -> None:
    # Los enlaces borrados no vuelven: eran secretos en claro
    op.drop_column("users", "password_reset_window_started_at")
    op.drop_column("users", "password_reset_emails_in_window")
    op.drop_column("users", "register_attempt_notice_at")
    op.drop_column("users", "verification_token_expires_at")
