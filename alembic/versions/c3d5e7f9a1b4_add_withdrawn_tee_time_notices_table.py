"""add withdrawn_tee_time_notices table

Quien perdio su aviso de salida de una ronda por un cambio en ella (se quedo sin
partido o sin grupo) y aun no lo ha recuperado. Reasignar rivales de la Ryder
son dos `PUT matches/{id}/players`: entre los dos, quien se queda sin partido
pierde su aviso, y en el segundo le nacia uno con `changed: false` («ya tienes
partido») en vez de `changed: true` (prueba de punta a punta, 22 oct 2026).

Una fila por (jugador, ronda). Se olvida al recuperar la salida, con la baja del
jugador y con la cancelacion o el borrado del torneo. Tabla nueva y vacia: el
codigo viejo no la conoce, asi que desplegar en cualquier orden es seguro.

Revision ID: c3d5e7f9a1b4
Revises: b2e4d6f8a0c3
Create Date: 2026-10-22

"""

import sqlalchemy as sa
from alembic import op

revision = "c3d5e7f9a1b4"
down_revision = "b2e4d6f8a0c3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "withdrawn_tee_time_notices",
        sa.Column("user_id", sa.CHAR(36), nullable=False),
        sa.Column("round_id", sa.String(36), nullable=False),
        sa.Column("competition_id", sa.String(36), nullable=False),
        sa.Column(
            "withdrawn_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("timezone('utc', now())"),
        ),
        sa.PrimaryKeyConstraint("user_id", "round_id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )
    # La publicacion de una ronda pregunta por la ronda; la baja y la
    # cancelacion, por el torneo
    op.create_index(
        "ix_withdrawn_tee_time_notices_round", "withdrawn_tee_time_notices", ["round_id"]
    )
    op.create_index(
        "ix_withdrawn_tee_time_notices_competition",
        "withdrawn_tee_time_notices",
        ["competition_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_withdrawn_tee_time_notices_competition", table_name="withdrawn_tee_time_notices"
    )
    op.drop_index("ix_withdrawn_tee_time_notices_round", table_name="withdrawn_tee_time_notices")
    op.drop_table("withdrawn_tee_time_notices")
