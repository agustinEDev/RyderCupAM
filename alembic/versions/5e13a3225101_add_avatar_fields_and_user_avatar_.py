"""add avatar fields and user avatar uploads table

Revision ID: 5e13a3225101
Revises: b8e2f4a6c1d7
Create Date: 2026-07-29 15:16:36.507356

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '5e13a3225101'
down_revision: str | None = 'b8e2f4a6c1d7'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Tabla user_avatar_uploads primero: users.active_avatar_upload_id la referencia.
    op.create_table(
        "user_avatar_uploads",
        sa.Column("id", sa.CHAR(36), primary_key=True),
        sa.Column(
            "user_id",
            sa.CHAR(36),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("image_data", sa.LargeBinary(), nullable=False),
        sa.Column("content_type", sa.String(length=50), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index(
        "ix_user_avatar_uploads_user_created",
        "user_avatar_uploads",
        ["user_id", "created_at"],
    )

    # 2. Columnas de avatar en users (avatar_source/avatar_preset_id: catálogo fijo,
    #    no requieren tabla propia; active_avatar_upload_id sí referencia la tabla anterior).
    op.add_column(
        "users",
        sa.Column("avatar_source", sa.String(length=10), nullable=False, server_default="NONE"),
    )
    op.add_column(
        "users",
        sa.Column("avatar_preset_id", sa.Integer(), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column("active_avatar_upload_id", sa.CHAR(36), nullable=True),
    )
    op.create_foreign_key(
        "fk_users_active_avatar_upload_id",
        "users",
        "user_avatar_uploads",
        ["active_avatar_upload_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_users_active_avatar_upload_id", "users", type_="foreignkey")
    op.drop_column("users", "active_avatar_upload_id")
    op.drop_column("users", "avatar_preset_id")
    op.drop_column("users", "avatar_source")
    op.drop_index("ix_user_avatar_uploads_user_created", table_name="user_avatar_uploads")
    op.drop_table("user_avatar_uploads")
