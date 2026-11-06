"""user device: when it sent the new sign-in notice

Release de dispositivos (BE #737): el correo de «nuevo inicio de sesión» sale como
mucho una vez por hora, contado desde el último que se envió. Se apunta en el
dispositivo que avisó.

Una columna nula: en Postgres 11+ no reescribe la tabla, va en la transacción.

Revision ID: d6f8b0c2e4a7
Revises: c5e7a9b1d3f6
Create Date: 2026-11-05

"""

import sqlalchemy as sa
from alembic import op

revision = "d6f8b0c2e4a7"
down_revision = "c5e7a9b1d3f6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("user_devices", sa.Column("new_login_notice_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column("user_devices", "new_login_notice_at")
