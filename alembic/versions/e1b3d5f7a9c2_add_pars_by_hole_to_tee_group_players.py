"""Add pars_by_hole to tee_group_players (BE #251, PR 5)

El par de cada hoyo desde las barras de cada jugador, en la foto de su
partida (decidido el 9 oct 2026, P12): 25 campos federados tienen par distinto
según la barra, y si alguien edita el campo durante la competición los
resultados no deben cambiar. Sin él no hay puntos Stableford ni «par» en Medal.

Las partidas aún no han llegado a producción, pero sí a develop (PR 4): las
que ya se generaron reciben el par de la tarjeta de referencia de su campo,
la de la primera salida con hoyos, como `GolfCourse.reference_card`. Sin
esto, `upgrade` fallaba en cualquier base con partidas.

Revision ID: e1b3d5f7a9c2
Revises: d0a2c4e6f8b1
Create Date: 2026-10-09

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "e1b3d5f7a9c2"
down_revision = "d0a2c4e6f8b1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """El par por hoyo de cada jugador de una partida."""
    op.add_column(
        "tee_group_players",
        sa.Column("pars_by_hole", postgresql.JSONB(), nullable=True),
    )
    # SQL puro: no lee nada, así que vale también en el guion offline
    op.execute(
        """
        UPDATE tee_group_players AS jugador
        SET pars_by_hole = (
            SELECT jsonb_agg(hoyo.par ORDER BY hoyo.hole_number)
            FROM golf_course_tee_holes AS hoyo
            WHERE hoyo.tee_id = (
                SELECT salida.id
                FROM golf_course_tees AS salida
                JOIN rounds AS franja ON franja.golf_course_id = salida.golf_course_id
                WHERE franja.id = jugador.round_id
                  AND EXISTS (
                      SELECT 1 FROM golf_course_tee_holes AS h WHERE h.tee_id = salida.id
                  )
                ORDER BY salida.id
                LIMIT 1
            )
        )
        """
    )
    op.alter_column("tee_group_players", "pars_by_hole", nullable=False)


def downgrade() -> None:
    """Quita el par por hoyo."""
    op.drop_column("tee_group_players", "pars_by_hole")
