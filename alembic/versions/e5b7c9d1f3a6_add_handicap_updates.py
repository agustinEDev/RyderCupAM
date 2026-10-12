"""Add handicap_updates (BE #251)

El refresco con la RFEG deja de hacerse a las 3:00 de cada día de juego y pasa
a hacerse al cerrar las inscripciones (decidido el 7 oct 2026), y luego con el
botón del organizador o a una hora programada. Cada vez es una actualización
con su estado, y lo que contestó la RFEG por cada jugador cuelga de ella, con
los intentos.

`handicap_refreshes` se crea de nuevo: nunca llegó a producción, y lo apuntado
por día no sirve para el modelo nuevo.

Revision ID: e5b7c9d1f3a6
Revises: d4a6b8c0e2f3
Create Date: 2026-10-07

"""

import sqlalchemy as sa
from alembic import op

revision = "e5b7c9d1f3a6"
down_revision = "d4a6b8c0e2f3"
branch_labels = None
depends_on = None


def _jugador() -> sa.Column:
    return sa.Column(
        "user_id",
        sa.CHAR(length=36),
        sa.ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )


def _resultado() -> list[sa.Column]:
    return [
        sa.Column("result", sa.String(30), nullable=False),
        sa.Column("refreshed_at", sa.DateTime(timezone=True), nullable=False),
    ]


def upgrade() -> None:
    """Las actualizaciones, y sus resultados por jugador."""
    op.drop_table("handicap_refreshes")
    op.create_table(
        "handicap_updates",
        sa.Column("id", sa.CHAR(length=36), primary_key=True),
        sa.Column(
            "competition_id",
            sa.CHAR(length=36),
            sa.ForeignKey("competitions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("origin", sa.String(30), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_handicap_updates_competition_id", "handicap_updates", ["competition_id"]
    )
    op.create_table(
        "handicap_refreshes",
        sa.Column(
            "update_id",
            sa.CHAR(length=36),
            sa.ForeignKey("handicap_updates.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        _jugador(),
        sa.Column("attempts", sa.Integer(), nullable=False),
        *_resultado(),
    )


def downgrade() -> None:
    """Vuelve a una fila por torneo, día y jugador."""
    op.drop_table("handicap_refreshes")
    op.drop_index("ix_handicap_updates_competition_id", table_name="handicap_updates")
    op.drop_table("handicap_updates")
    op.create_table(
        "handicap_refreshes",
        sa.Column(
            "competition_id",
            sa.CHAR(length=36),
            sa.ForeignKey("competitions.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("play_date", sa.Date(), primary_key=True),
        _jugador(),
        *_resultado(),
    )
