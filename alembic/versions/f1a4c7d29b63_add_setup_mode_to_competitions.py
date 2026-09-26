"""add setup mode to competitions

Cuanto monta la aplicacion por su cuenta (FE #695): AUTOMATIC, MANUAL o
RYDER_CUP. Se elige al crear el torneo y se puede cambiar mientras las
inscripciones sigan abiertas.

`RYDER_CUP` por defecto, y asi se quedan las que ya existan: es lo que son
todas hoy —equipos, capitanes y calendario a mano o mixto—, de modo que nadie
ve cambiar su torneo por no haber contestado a una pregunta que no existia.

Revision ID: f1a4c7d29b63
Revises: e4b8c1f92a07
Create Date: 2026-09-22

"""

import sqlalchemy as sa

from alembic import op

revision = "f1a4c7d29b63"
down_revision = "e4b8c1f92a07"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "competitions",
        sa.Column("setup_mode", sa.String(20), nullable=False, server_default="RYDER_CUP"),
    )


def downgrade() -> None:
    op.drop_column("competitions", "setup_mode")
