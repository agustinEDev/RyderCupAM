"""Recreate invitations FKs to users with ON DELETE CASCADE

Revision ID: c7d1e4f8a2b6
Revises: 2a33bf8e43ff
Create Date: 2026-08-04 12:00:00.000000

Las dos FKs de `invitations` hacia `users` se crearon sin `ON DELETE`
(ver f6b8c4d2e3a5), asi que borrar una cuenta referenciada por una
invitacion abortaba el DELETE con ForeignKeyViolationError (500 en
`DELETE /api/v1/admin/users/{id}`).

Se recrean ambas con CASCADE: al borrar la cuenta desaparecen tanto las
invitaciones que envio como las que recibio. Las invitaciones dirigidas
solo a un email (invitee_user_id NULL) no se ven afectadas.

"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "c7d1e4f8a2b6"
down_revision = "2a33bf8e43ff"
branch_labels = None
depends_on = None


INVITER_FK = "invitations_inviter_id_fkey"
INVITEE_FK = "invitations_invitee_user_id_fkey"


def upgrade() -> None:
    op.drop_constraint(INVITER_FK, "invitations", type_="foreignkey")
    op.create_foreign_key(
        INVITER_FK,
        "invitations",
        "users",
        ["inviter_id"],
        ["id"],
        ondelete="CASCADE",
    )

    op.drop_constraint(INVITEE_FK, "invitations", type_="foreignkey")
    op.create_foreign_key(
        INVITEE_FK,
        "invitations",
        "users",
        ["invitee_user_id"],
        ["id"],
        ondelete="CASCADE",
    )


def downgrade() -> None:
    op.drop_constraint(INVITEE_FK, "invitations", type_="foreignkey")
    op.create_foreign_key(
        INVITEE_FK,
        "invitations",
        "users",
        ["invitee_user_id"],
        ["id"],
    )

    op.drop_constraint(INVITER_FK, "invitations", type_="foreignkey")
    op.create_foreign_key(
        INVITER_FK,
        "invitations",
        "users",
        ["inviter_id"],
        ["id"],
    )
