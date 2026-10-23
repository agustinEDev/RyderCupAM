"""quick match started_at, to close it on its own

Decision de Agustin del 23 oct 2026: la partida rapida que nadie termina se
cierra sola al acabar el dia siguiente al que empezo, en la hora del campo.
Hasta ahora no se guardaba cuando empezaba: `started_at` lo apunta al empezar.

Las que ya estan en juego toman su `updated_at`: lo escribio el inicio, o algo
posterior (ocultarla, fijar los handicaps), nunca algo anterior. Con
`created_at`, una partida creada el viernes y empezada el domingo antes del
despliegue se cerraria en la primera pasada (code-review). Las demas quedan a
NULL: las pendientes cuentan desde `created_at` y las terminadas no cuentan.

Una columna nula y un UPDATE sobre pocas filas: va en la transaccion.

Revision ID: f8a0c2e4b6d7
Revises: e5f7a9b1c3d6
Create Date: 2026-10-23

"""

import sqlalchemy as sa
from alembic import op

revision = "f8a0c2e4b6d7"
down_revision = "e5f7a9b1c3d6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("quick_matches", sa.Column("started_at", sa.DateTime(), nullable=True))
    op.execute("UPDATE quick_matches SET started_at = updated_at WHERE status = 'IN_PROGRESS'")


def downgrade() -> None:
    op.drop_column("quick_matches", "started_at")
