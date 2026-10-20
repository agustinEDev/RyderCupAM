"""Add tournament_type to competitions (BE #251)

Decidido el 1 oct 2026: modalidad → tipo de torneo. La competición guarda el
tipo (RYDER_CUP, STABLEFORD o MEDAL) y la modalidad se deriva de él.

Todas las que existen son Ryder Cup: la columna nace con ese valor por defecto
y no hace falta tocar ninguna fila.

Un Stableford o un Medal no tiene equipos, ni modo de montaje, ni reparto: esas
columnas pasan a admitir vacío. Las Ryder Cup siguen llenándolas.

Revision ID: a7d3e9f2c4b1
Revises: e4b7c2d91f36
Create Date: 2026-10-03

"""

import sqlalchemy as sa
from alembic import op

revision = "a7d3e9f2c4b1"
down_revision = "e4b7c2d91f36"
branch_labels = None
depends_on = None

COLUMNAS_DE_LA_RYDER = (
    ("team_1_name", sa.String(100)),
    ("team_2_name", sa.String(100)),
    ("team_assignment", sa.String(20)),
    ("setup_mode", sa.String(20)),
)


def upgrade() -> None:
    """Añade el tipo y deja vacías las columnas de la Ryder para los demás tipos."""
    op.add_column(
        "competitions",
        sa.Column(
            "tournament_type",
            sa.String(20),
            nullable=False,
            server_default="RYDER_CUP",
        ),
    )
    for nombre, tipo in COLUMNAS_DE_LA_RYDER:
        op.alter_column("competitions", nombre, existing_type=tipo, nullable=True)
    # El reparto tenía «MANUAL» por defecto y el modo «RYDER_CUP» en la base de
    # datos: en un torneo sin equipos, un valor puesto por defecto mentiría. El
    # del reparto, además, estaba mal escrito: guardaba el texto 'MANUAL' con
    # las comillas dentro (los mappers no lo declaran y la app siempre lo escribe)
    for nombre in ("setup_mode", "team_assignment"):
        op.alter_column("competitions", nombre, existing_type=sa.String(20), server_default=None)


def downgrade() -> None:
    """
    Vuelve a exigir las columnas de la Ryder y quita el tipo.

    Falla si ya hay torneos de stroke play guardados: no tienen equipos que
    poner, y bajar la versión no puede inventárselos. Se borran a mano antes.
    """
    op.alter_column(
        "competitions",
        "setup_mode",
        existing_type=sa.String(20),
        server_default="RYDER_CUP",
    )
    # Se restaura bien escrito, no con las comillas dentro
    op.alter_column(
        "competitions",
        "team_assignment",
        existing_type=sa.String(20),
        server_default="MANUAL",
    )
    for nombre, tipo in COLUMNAS_DE_LA_RYDER:
        op.alter_column("competitions", nombre, existing_type=tipo, nullable=False)
    op.drop_column("competitions", "tournament_type")
