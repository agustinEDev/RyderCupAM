"""Add played to tee_group_players (BE #550, 13 oct 2026)

Decidido con Agustín el 13 oct 2026: la marca «ha jugado» de cada jugador de una
partida. Se enciende cuando anota algo desde su pantalla (su golpe o el de quien
marca) y no se apaga; junto con lo que haya en su tarjeta decide si se le puede
marcar no presentado y cómo queda al cerrar la franja. Lo que el organizador
anota o borra no la toca.

Las filas que ya existen la toman de lo ya anotado: su propio lado lo metió él,
o metió el lado del marcador de otro de su partida. Solo SQL plano: cabe en el
guion del modo offline.

Revision ID: e8b0c2d4f6a7
Revises: d5f7a9b1c3e6
Create Date: 2026-10-13

"""

import sqlalchemy as sa
from alembic import op

revision = "e8b0c2d4f6a7"
down_revision = "d5f7a9b1c3e6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """La marca, apagada; encendida en quien ya anotó desde su pantalla."""
    op.add_column(
        "tee_group_players",
        sa.Column("played", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.execute(
        """
        UPDATE tee_group_players AS p
        SET played = TRUE
        WHERE EXISTS (
            SELECT 1 FROM tee_group_hole_scores AS h
            WHERE h.group_id = p.group_id
              AND (
                (h.user_id = p.user_id AND h.own_submitted AND h.own_by = p.user_id)
                OR (h.user_id <> p.user_id AND h.marker_submitted AND h.marker_by = p.user_id)
              )
        )
        """
    )


def downgrade() -> None:
    """Quita la columna."""
    op.drop_column("tee_group_players", "played")
