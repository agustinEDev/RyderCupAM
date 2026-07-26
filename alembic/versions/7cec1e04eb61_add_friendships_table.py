"""Add friendships table

Revision ID: 7cec1e04eb61
Revises: 117fa75bd4ee
Create Date: 2026-07-26 12:00:00.000000

"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "7cec1e04eb61"
down_revision = "117fa75bd4ee"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "friendships",
        sa.Column("id", sa.CHAR(36), nullable=False),
        sa.Column("requester_id", sa.CHAR(36), nullable=False),
        sa.Column("addressee_id", sa.CHAR(36), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="PENDING"),
        sa.Column("blocked_by", sa.CHAR(36), nullable=True),
        sa.Column("responded_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["requester_id"],
            ["users.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["addressee_id"],
            ["users.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["blocked_by"],
            ["users.id"],
            ondelete="CASCADE",
        ),
        sa.CheckConstraint(
            "requester_id <> addressee_id",
            name="ck_friendships_no_self_friend",
        ),
        sa.CheckConstraint(
            "blocked_by IS NULL OR blocked_by = requester_id OR blocked_by = addressee_id",
            name="ck_friendships_blocked_by_participant",
        ),
    )

    # Indexes for common queries
    op.create_index(
        "ix_friendships_requester_id",
        "friendships",
        ["requester_id"],
    )
    op.create_index(
        "ix_friendships_addressee_id",
        "friendships",
        ["addressee_id"],
    )
    op.create_index(
        "ix_friendships_status",
        "friendships",
        ["status"],
    )

    # Solo una relacion (en cualquier estado) por pareja de usuarios, en cualquier direccion.
    # Se normaliza con LEAST/GREATEST para que (A,B) y (B,A) colisionen.
    op.execute(
        "CREATE UNIQUE INDEX uq_friendship_pair "
        "ON friendships (LEAST(requester_id, addressee_id), GREATEST(requester_id, addressee_id))"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_friendship_pair")
    op.drop_index("ix_friendships_status", table_name="friendships")
    op.drop_index("ix_friendships_addressee_id", table_name="friendships")
    op.drop_index("ix_friendships_requester_id", table_name="friendships")
    op.drop_table("friendships")
