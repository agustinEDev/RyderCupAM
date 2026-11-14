"""invitations: whether the organizer typed an email or picked a user

Auditoría de la fase 6, B-01 y B-03: invitando por id se leía el correo de cualquier
usuario, y por correo se sabía si ese correo tenía cuenta. Lo que ve el organizador
depende ahora de cómo la mandó (decidido por Agustín el 14 nov 2026), y la invitación no
lo guardaba.

Las que ya existen: con usuario, «por id»; sin usuario, «por correo». Una mandada por
correo a una cuenta verificada quedó con usuario y pasa por «por id»: el organizador verá
su nombre, que es lo que ya veía.

Columna con valor por defecto constante: en Postgres 11+ no reescribe la tabla. La
release anterior sigue funcionando con la tabla migrada (no la lee, y sus INSERT toman
el valor por defecto).

Revision ID: d4f6a8c0e2b5
Revises: b7e9d1f3a5c8
Create Date: 2026-11-14

"""

import sqlalchemy as sa

from alembic import op

revision = "d4f6a8c0e2b5"
down_revision = "b7e9d1f3a5c8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Si una transacción larga tuviera `invitations` bloqueada, mejor fallar a los 5 s
    # que dejar las invitaciones en cola detrás del ALTER. SET LOCAL: solo aquí
    op.execute("SET LOCAL lock_timeout = '5s'")
    op.add_column(
        "invitations",
        sa.Column("sent_by_email", sa.Boolean(), nullable=False, server_default="false"),
    )
    op.execute("UPDATE invitations SET sent_by_email = true WHERE invitee_user_id IS NULL")


def downgrade() -> None:
    op.drop_column("invitations", "sent_by_email")
