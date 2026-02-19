"""Add invitations table

Revision ID: f6b8c4d2e3a5
Revises: e5a7b9c3d1f4
Create Date: 2026-02-18 16:30:00.000000

"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "f6b8c4d2e3a5"
down_revision = "e5a7b9c3d1f4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "invitations",
        sa.Column("id", sa.CHAR(36), nullable=False),
        sa.Column("competition_id", sa.CHAR(36), nullable=False),
        sa.Column("inviter_id", sa.CHAR(36), nullable=False),
        sa.Column("invitee_email", sa.String(254), nullable=False),
        sa.Column("invitee_user_id", sa.CHAR(36), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="PENDING"),
        sa.Column("personal_message", sa.Text(), nullable=True),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("responded_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["competition_id"],
            ["competitions.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["inviter_id"],
            ["users.id"],
        ),
        sa.ForeignKeyConstraint(
            ["invitee_user_id"],
            ["users.id"],
        ),
    )

    # Indexes for common queries
    op.create_index(
        "ix_invitations_competition_id",
        "invitations",
        ["competition_id"],
    )
    op.create_index(
        "ix_invitations_invitee_email",
        "invitations",
        ["invitee_email"],
    )
    op.create_index(
        "ix_invitations_invitee_user_id",
        "invitations",
        ["invitee_user_id"],
    )
    op.create_index(
        "ix_invitations_status",
        "invitations",
        ["status"],
    )
    op.create_index(
        "ix_invitations_expires_at",
        "invitations",
        ["expires_at"],
    )

    # Partial unique index: only one PENDING invitation per email+competition
    op.execute(
        "CREATE UNIQUE INDEX uq_invitation_pending_email_competition "
        "ON invitations (competition_id, invitee_email) "
        "WHERE status = 'PENDING'"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_invitation_pending_email_competition")
    op.drop_index("ix_invitations_expires_at", table_name="invitations")
    op.drop_index("ix_invitations_status", table_name="invitations")
    op.drop_index("ix_invitations_invitee_user_id", table_name="invitations")
    op.drop_index("ix_invitations_invitee_email", table_name="invitations")
    op.drop_index("ix_invitations_competition_id", table_name="invitations")
    op.drop_table("invitations")
