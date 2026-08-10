"""add activity_events table

Revision ID: d4e8f1a3b7c9
Revises: c7d1e4f8a2b6
Create Date: 2026-08-10

Feed de actividad entre amigos (BE #175). Guarda los logros que se publican:
birdies, eagles, hoyos en uno, campos estrenados, récords personales y el
primer torneo.

Dos detalles del diseño que la tabla refleja:

- `payload` es JSONB porque cada tipo de evento lleva un detalle distinto
  (cuántos birdies y en qué hoyos, qué diferencial batió al anterior). Añadir un
  tipo nuevo no debería exigir una migración.
- La restricción única sobre `(user_id, source_match_id, type)` es lo que impide
  que reprocesar una partida llene el feed de entradas repetidas. `source_match_id`
  es NOT NULL justamente para que esa restricción sirva: en Postgres un NULL no
  iguala a otro NULL, así que las filas sin partida se le escaparían todas. Todos
  los logros nacen de una vuelta terminada, así que no deja fuera ningún caso.
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "d4e8f1a3b7c9"
down_revision = "c7d1e4f8a2b6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "activity_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", sa.CHAR(36), nullable=False),
        sa.Column("type", sa.String(30), nullable=False),
        sa.Column("occurred_at", sa.DateTime(), nullable=False),
        sa.Column(
            "payload",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="{}",
        ),
        sa.Column("source_match_id", sa.String(36), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint(
            "user_id", "source_match_id", "type", name="uq_activity_events_match_type"
        ),
    )
    # El feed siempre pregunta lo mismo: eventos de estos jugadores, del más
    # reciente al más antiguo
    op.create_index(
        "ix_activity_events_user_occurred",
        "activity_events",
        ["user_id", "occurred_at"],
    )

    # Cuándo miró cada jugador su feed por última vez. De aquí sale el aviso de
    # novedades: contar lo publicado después de esta fecha. Nulo significa que
    # todavía no lo ha abierto nunca.
    op.add_column("users", sa.Column("feed_last_seen_at", sa.DateTime(), nullable=True))
    # Interruptor para no publicar. Activado por defecto: es una aplicación entre
    # amigos y el feed nacería vacío de otro modo.
    op.add_column(
        "users",
        sa.Column(
            "share_activity", sa.Boolean(), nullable=False, server_default=sa.true()
        ),
    )


def downgrade() -> None:
    op.drop_column("users", "share_activity")
    op.drop_column("users", "feed_last_seen_at")
    op.drop_index("ix_activity_events_user_occurred", table_name="activity_events")
    op.drop_table("activity_events")
