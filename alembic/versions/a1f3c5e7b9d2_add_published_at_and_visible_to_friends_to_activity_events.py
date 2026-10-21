"""add published_at and visible_to_friends to activity_events

`occurred_at` dice cuándo se jugó: el día de la ronda en un torneo, la creación
de la partida rápida. El aviso de novedades lo comparaba con la última visita
al feed, así que lo que se publicaba después de mirar —un torneo que cierra días
después de sus vueltas, una partida que se termina horas después de crearla—
no contaba nunca, y el feed salía desordenado. `published_at` es cuándo llegó al
feed, y por ella se ordena y se cuenta.

**Relleno con `occurred_at`, no con la hora de la migración.** Con la hora de
ahora, todo el historial pasaría por recién publicado: el aviso contaría logros
de hace meses y el feed los pondría arriba. Con `occurred_at` cada fila vieja
queda donde ya estaba, y los cursores que tengan los clientes siguen valiendo.

El valor por defecto en el servidor (`timezone('utc', now())`, la hora UTC sin
zona, como las que escribe la aplicación) cubre al código viejo que siga
insertando mientras dura el despliegue.

`visible_to_friends` (decidido con Agustín el 21 oct 2026): con la publicación
apagada el logro se guarda igual, pero solo para su autor, y encenderla después
no lo destapa. Las filas que existen hoy son todas de jugadores que publicaban
—apagar las borraba—, así que nacen visibles.

Solo DDL y un UPDATE: cabe en el guion del modo offline, y va en la transacción
de la migración. El índice nuevo va aparte, CONCURRENTLY (b2e4d6f8a0c3).

Revision ID: a1f3c5e7b9d2
Revises: e7f9a1b3c5d7
Create Date: 2026-10-21

"""

import sqlalchemy as sa
from alembic import op

revision = "a1f3c5e7b9d2"
down_revision = "e7f9a1b3c5d7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Mejor fallar a los 5 s que dejar la app esperando detrás del ALTER si una
    # transacción larga tuviera la tabla bloqueada. SET LOCAL: solo aquí dentro
    op.execute("SET LOCAL lock_timeout = '5s'")
    op.add_column("activity_events", sa.Column("published_at", sa.DateTime(), nullable=True))
    op.execute("UPDATE activity_events SET published_at = occurred_at")
    op.alter_column(
        "activity_events",
        "published_at",
        server_default=sa.text("timezone('utc', now())"),
        nullable=False,
    )
    op.add_column(
        "activity_events",
        sa.Column(
            "visible_to_friends",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
    )


def downgrade() -> None:
    op.drop_column("activity_events", "visible_to_friends")
    op.drop_column("activity_events", "published_at")
