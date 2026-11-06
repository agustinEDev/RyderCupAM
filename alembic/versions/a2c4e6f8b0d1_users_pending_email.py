"""users: the pending email change

#749: cambiar el correo ya no lo pone en la cuenta sin verificar. El nuevo espera en
`pending_email` hasta que se confirma desde su dirección (`pending_email_token`, que
caduca en `pending_email_expires_at`, 24 horas).

Columnas nulas: en Postgres 11+ no reescriben la tabla, van en la transacción.

Revision ID: a2c4e6f8b0d1
Revises: e1a3c5d7f9b2
Create Date: 2026-11-07

"""

import sqlalchemy as sa
from alembic import op

revision = "a2c4e6f8b0d1"
down_revision = "e1a3c5d7f9b2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("pending_email", sa.String(255), nullable=True))
    op.add_column("users", sa.Column("pending_email_token", sa.String(255), nullable=True))
    op.add_column("users", sa.Column("pending_email_expires_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "pending_email_expires_at")
    op.drop_column("users", "pending_email_token")
    op.drop_column("users", "pending_email")
