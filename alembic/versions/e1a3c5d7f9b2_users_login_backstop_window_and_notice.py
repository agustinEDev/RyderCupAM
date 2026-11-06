"""users: the failed-login backstop window and its notice

BE #732: los fallos de cada red se frenan por correo + red, en memoria. El contador
de la cuenta pasa a ser el RESPALDO de todas las redes juntas: 50 fallos en una hora,
y 150 en 24 horas contra el ataque lento.
- `failed_login_window_started_at`: el principio de esa hora;
- `failed_login_day_attempts` y `failed_login_day_window_started_at`: el contador
  de 24 horas y su principio;
- `failed_login_notice_at`: el último correo de intentos fallidos (uno por hora).

Columnas nulas o con valor por defecto constante: en Postgres 11+ no reescriben la
tabla, van en la transacción.

Revision ID: e1a3c5d7f9b2
Revises: d6f8b0c2e4a7
Create Date: 2026-11-06

"""

import sqlalchemy as sa
from alembic import op

revision = "e1a3c5d7f9b2"
down_revision = "d6f8b0c2e4a7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users", sa.Column("failed_login_window_started_at", sa.DateTime(), nullable=True)
    )
    op.add_column("users", sa.Column("failed_login_notice_at", sa.DateTime(), nullable=True))
    op.add_column(
        "users",
        sa.Column("failed_login_day_attempts", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "users", sa.Column("failed_login_day_window_started_at", sa.DateTime(), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("users", "failed_login_day_window_started_at")
    op.drop_column("users", "failed_login_day_attempts")
    op.drop_column("users", "failed_login_notice_at")
    op.drop_column("users", "failed_login_window_started_at")
