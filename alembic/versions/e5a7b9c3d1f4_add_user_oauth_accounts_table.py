"""add user_oauth_accounts table and make password nullable

Revision ID: e5a7b9c3d1f4
Revises: d4f6a8b2c9e3
Create Date: 2026-02-16 08:00:00.000000

Sprint 3 - Google OAuth:
- Creates user_oauth_accounts table for storing OAuth provider links
- Makes users.password nullable to support OAuth-only users
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e5a7b9c3d1f4"
down_revision: str | None = "d4f6a8b2c9e3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Create user_oauth_accounts table
    op.create_table(
        "user_oauth_accounts",
        sa.Column("id", sa.CHAR(36), primary_key=True),
        sa.Column(
            "user_id",
            sa.CHAR(36),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("provider", sa.String(20), nullable=False),
        sa.Column("provider_user_id", sa.String(255), nullable=False),
        sa.Column("provider_email", sa.String(255), nullable=False),
        sa.Column("created_at", sa.DateTime, nullable=False),
    )

    # Unique constraint: one provider account can only be linked once
    op.create_unique_constraint(
        "uq_oauth_provider_user",
        "user_oauth_accounts",
        ["provider", "provider_user_id"],
    )

    # Index for user_id lookups
    op.create_index(
        "ix_oauth_accounts_user_id",
        "user_oauth_accounts",
        ["user_id"],
    )

    # Make users.password nullable for OAuth-only users
    op.alter_column(
        "users",
        "password",
        existing_type=sa.String(255),
        nullable=True,
    )


def downgrade() -> None:
    # Pre-check: fail fast if any users have NULL passwords (OAuth-only users)
    conn = op.get_bind()
    result = conn.execute(
        sa.text("SELECT COUNT(*) FROM users WHERE password IS NULL")
    )
    null_password_count = result.scalar()
    if null_password_count > 0:
        raise RuntimeError(
            f"Cannot downgrade: {null_password_count} user(s) have NULL passwords "
            f"(OAuth-only accounts). Assign passwords to these users before downgrading."
        )

    # Revert password to NOT NULL (safe — no NULL values exist)
    op.alter_column(
        "users",
        "password",
        existing_type=sa.String(255),
        nullable=False,
    )

    # Drop table (cascades indexes and constraints)
    op.drop_index("ix_oauth_accounts_user_id", table_name="user_oauth_accounts")
    op.drop_constraint("uq_oauth_provider_user", "user_oauth_accounts", type_="unique")
    op.drop_table("user_oauth_accounts")
