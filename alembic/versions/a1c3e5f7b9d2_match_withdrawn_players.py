"""match withdrawn players, for a fourball with an absent player

Decision de Agustin del 24-25 oct 2026: en un fourball de torneo, el jugador
que no se presenta o se va se marca como retirado. Su bola deja de contar en
los hoyos que no tenia validados y su bando juega con la de su pareja. Con la
regla de las cuatro bolas (BE #656), un ausente dejaba el partido sin avanzar.

La lista de retirados va en el partido, como las tarjetas entregadas: JSONB
nulo, que se lee como ninguno. Y de los que vuelven, los hoyos que se cerraron
sin su bola, que se quedan asi (`holes_without_ball`, {user_id: [hoyos]}). Dos
columnas nulas sin reescribir filas: va en la transaccion.

Revision ID: a1c3e5f7b9d2
Revises: f8a0c2e4b6d7
Create Date: 2026-10-25

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "a1c3e5f7b9d2"
down_revision = "f8a0c2e4b6d7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "matches",
        sa.Column("withdrawn_player_ids", postgresql.JSONB(), nullable=True),
    )
    op.add_column(
        "matches",
        sa.Column("holes_without_ball", postgresql.JSONB(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("matches", "holes_without_ball")
    op.drop_column("matches", "withdrawn_player_ids")
