"""add withdrawn_hidden_achievements table

Los logros que se publicaron ocultos (con «compartir actividad» apagado) y se
retiraron: al reabrir el torneo, o al llevarse otro mas antiguo «campo nuevo» o
«primer torneo». Reabrir y volver a cerrar el mismo torneo los publicaba otra
vez con el interruptor de ahora, y si se habia vuelto a encender sus amigos los
veian (fallo del probador, 23 oct 2026). Con esta tabla, el mismo logro
(jugador, tipo y origen) vuelve oculto.

Una fila por logro retirado oculto; se gasta al volver a publicarlo. Tabla
nueva y vacia: el codigo viejo no la conoce, asi que desplegar en cualquier
orden es seguro (lo que el codigo viejo retire mientras tanto no queda
apuntado, como hasta hoy).

Revision ID: d4e6f8a0b2c5
Revises: c3d5e7f9a1b4
Create Date: 2026-10-23

"""

import sqlalchemy as sa
from alembic import op

revision = "d4e6f8a0b2c5"
down_revision = "c3d5e7f9a1b4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # La clave primaria empieza por el jugador: sirve tambien al borrado en
    # cascada de su cuenta
    op.create_table(
        "withdrawn_hidden_achievements",
        sa.Column("user_id", sa.CHAR(36), nullable=False),
        sa.Column("source_match_id", sa.String(36), nullable=False),
        sa.Column("type", sa.String(30), nullable=False),
        sa.Column(
            "withdrawn_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("timezone('utc', now())"),
        ),
        sa.PrimaryKeyConstraint("user_id", "source_match_id", "type"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )


def downgrade() -> None:
    op.drop_table("withdrawn_hidden_achievements")
