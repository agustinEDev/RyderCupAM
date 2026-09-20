"""add visibility to competitions

Publica o privada (BE #318). Hasta ahora no existia la distincion: la pantalla
de explorar ensenaba la Ryder de unos amigos a cualquiera, y cualquiera podia
pedir plaza en ella.

`PRIVATE` por defecto, y asi se quedan todas las que ya existen: son torneos
entre amigos, y publicar el de alguien sin que lo pida no tiene vuelta atras.

Revision ID: d7a1e94c38b2
Revises: c5d2f83a71e9
Create Date: 2026-09-20

"""

import sqlalchemy as sa
from alembic import op

revision = "d7a1e94c38b2"
down_revision = "c5d2f83a71e9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "competitions",
        sa.Column("visibility", sa.String(20), nullable=False, server_default="PRIVATE"),
    )


def downgrade() -> None:
    op.drop_column("competitions", "visibility")
