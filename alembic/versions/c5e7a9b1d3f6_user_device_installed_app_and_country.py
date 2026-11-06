"""user device: installed app and country

Release de dispositivos (BE #737): la app instalada (PWA) y el navegador del
mismo móvil son dos dispositivos, y la pantalla dice cuál es cuál. Y el país
aproximado de la última conexión, el que da Cloudflare (CF-IPCountry) solo
cuando la petición trae su secreto (ADR-041).

Una booleana con valor por defecto y una columna nula: en Postgres 11+ ninguna
reescribe la tabla, van en la transacción.

Revision ID: c5e7a9b1d3f6
Revises: b4d6f8a0c2e5
Create Date: 2026-11-05

"""

import sqlalchemy as sa
from alembic import op

revision = "c5e7a9b1d3f6"
down_revision = "b4d6f8a0c2e5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "user_devices",
        sa.Column("installed_app", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column("user_devices", sa.Column("country_code", sa.String(2), nullable=True))


def downgrade() -> None:
    op.drop_column("user_devices", "country_code")
    op.drop_column("user_devices", "installed_app")
