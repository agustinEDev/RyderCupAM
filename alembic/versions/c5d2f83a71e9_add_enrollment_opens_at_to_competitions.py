"""add enrollment_opens_at to competitions

La hora a la que se abren solas las inscripciones (BE #319). Es hora LOCAL del
campo donde se juega, sin huso: «las nueve» son las nueve de alli, y la zona se
resuelve al leerla, con las coordenadas del campo.

Nullable porque la mayoria de los torneos no programan nada: entre amigos se
invita a alguien y con eso se abre.

Revision ID: c5d2f83a71e9
Revises: b4e91c72fa30
Create Date: 2026-09-20

"""

import sqlalchemy as sa
from alembic import op

revision = "c5d2f83a71e9"
down_revision = "b4e91c72fa30"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "competitions",
        sa.Column("enrollment_opens_at", sa.DateTime(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("competitions", "enrollment_opens_at")
