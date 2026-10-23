"""remember withdrawn achievements: date, hidden holes and course

Decisiones de Agustin del 23 oct 2026, tras la release social 1:

1. El mismo logro (jugador, tipo y vuelta) que se vuelve a publicar conserva
   su fecha: no sube ni cuenta como nuevo. Hace falta apuntar la fecha de
   TODO logro que se retira, no solo de los ocultos: `published_at`, y
   `hidden` dice si ademas estaba oculto. Las filas de la 2.38.0 eran todas
   de logros ocultos, de ahi `server_default true`.
2. «Campo nuevo» y «primer torneo» heredados nacen ocultos si el que se
   retiro lo estaba: `golf_course_id` dice de que campo era el «campo nuevo».
3. Lo oculto se recuerda por hoyo en birdie, eagle y hoyo en uno:
   `hidden_holes` (NULL = todo el logro, como en la 2.38.0).

La tabla no se renombra aunque ya no guarde solo lo oculto: el codigo viejo
sigue escribiendo en ella mientras dura el despliegue. Ese codigo trata todo
apunte como oculto y lo gasta, asi que un logro retirado por el codigo nuevo y
vuelto a publicar por el viejo en esa ventana de segundos queda oculto para
siempre y pierde su fecha. Volver a la 2.38.0 exige antes bajar esta migracion.

`activity_events.written_at`: cuando se escribio la fila. Como `published_at`
ya no es siempre la hora de escritura, quien publica un torneo mira esta para
saber si otra publicacion escribio mientras calculaba (la herencia de una
reapertura). Las filas de antes, con su `published_at`, que entonces lo era.

Solo DDL y un UPDATE sobre pocas filas: va en la transaccion de la migracion.

Revision ID: e5f7a9b1c3d6
Revises: d4e6f8a0b2c5
Create Date: 2026-10-23

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "e5f7a9b1c3d6"
down_revision = "d4e6f8a0b2c5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "withdrawn_hidden_achievements", sa.Column("published_at", sa.DateTime(), nullable=True)
    )
    op.add_column(
        "withdrawn_hidden_achievements",
        sa.Column("hidden", sa.Boolean(), nullable=False, server_default=sa.text("true")),
    )
    op.add_column(
        "withdrawn_hidden_achievements",
        sa.Column("hidden_holes", postgresql.JSONB(), nullable=True),
    )
    op.add_column(
        "withdrawn_hidden_achievements",
        sa.Column("golf_course_id", sa.String(36), nullable=True),
    )
    op.add_column(
        "activity_events",
        sa.Column(
            "written_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("timezone('utc', now())"),
        ),
    )
    op.execute("UPDATE activity_events SET written_at = published_at")


def downgrade() -> None:
    # Lo que se apunto visible no lo era: el codigo de la 2.38.0 lo leeria
    # como oculto
    op.execute("DELETE FROM withdrawn_hidden_achievements WHERE NOT hidden")
    op.drop_column("activity_events", "written_at")
    op.drop_column("withdrawn_hidden_achievements", "golf_course_id")
    op.drop_column("withdrawn_hidden_achievements", "hidden_holes")
    op.drop_column("withdrawn_hidden_achievements", "hidden")
    op.drop_column("withdrawn_hidden_achievements", "published_at")
