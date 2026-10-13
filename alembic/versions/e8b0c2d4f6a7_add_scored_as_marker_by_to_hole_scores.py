"""Add scored_as_marker_by to tee_group_hole_scores (BE #550, 13 oct 2026)

Decidido con Agustín el 13 oct 2026: quién anotó el lado del marcador desde su
pantalla de jugador, aparte de `marker_by`, que también cambia cuando el
organizador corrige. Dice quién estuvo en el campo aunque después corrijan o se
rehaga el círculo de marcadores. Nula en las filas que ya existen (el stroke play
no está en producción); cabe en el guion del modo offline.

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
    """Quién anotó como marcador."""
    op.add_column(
        "tee_group_hole_scores",
        sa.Column("scored_as_marker_by", sa.CHAR(length=36), nullable=True),
    )


def downgrade() -> None:
    """Quita la columna."""
    op.drop_column("tee_group_hole_scores", "scored_as_marker_by")
