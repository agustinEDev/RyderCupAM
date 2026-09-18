"""add timezone to competitions

La anotación de un partido se abre sola a una hora fija por sesión —mañana
06:00, tarde 12:00, noche 18:00— para que una vuelta no se pierda porque nadie
pulsó START con cobertura (BE #305). Esa hora es la LOCAL del campo, y las seis
de Canarias no son las seis de Madrid.

No se puede deducir del país: la tabla `countries` no guarda husos, y España
tiene dos. Por eso la zona va en la competición.

`Europe/Madrid` por defecto y NOT NULL: es donde se juega hoy, y así las
competiciones que ya existen abren a la hora correcta sin tocar nada. Cambiarla
desde la interfaz vendrá después; no hace falta para la península.

Revision ID: 7c3e91a45d18
Revises: 43bc18ca6df1
Create Date: 2026-09-18

"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "7c3e91a45d18"
down_revision = "43bc18ca6df1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "competitions",
        sa.Column(
            "timezone",
            sa.String(length=64),
            nullable=False,
            server_default="Europe/Madrid",
        ),
    )


def downgrade() -> None:
    op.drop_column("competitions", "timezone")
