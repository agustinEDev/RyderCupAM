"""add_user_devices_table

Revision ID: 50ccf425ff32
Revises: d850bb7f327d
Create Date: 2026-01-09 13:02:39.667716

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "50ccf425ff32"
down_revision: str | None = "d850bb7f327d"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Crea tabla user_devices para Device Fingerprinting."""
    op.create_table(
        "user_devices",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("device_name", sa.String(length=200), nullable=False),
        sa.Column("user_agent", sa.Text(), nullable=False),
        sa.Column("ip_address", sa.String(length=45), nullable=False),
        sa.Column("fingerprint_hash", sa.String(length=64), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("last_used_at", sa.DateTime(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )

    # Índice para búsquedas por usuario
    op.create_index("ix_user_devices_user_id", "user_devices", ["user_id"])

    # Índice único: previene dispositivos duplicados activos
    op.create_index(
        "ix_user_devices_unique_active_fingerprint",
        "user_devices",
        ["user_id", "fingerprint_hash"],
        unique=True,
        postgresql_where=sa.text("is_active = true"),
    )


def downgrade() -> None:
    """Elimina tabla user_devices."""
    op.drop_index(
        "ix_user_devices_unique_active_fingerprint", table_name="user_devices"
    )
    op.drop_index("ix_user_devices_user_id", table_name="user_devices")
    op.drop_table("user_devices")
