"""Add terms_accepted_at and terms_version to users (20 oct 2026)

Quién aceptó los Términos de uso, cuándo y qué versión. Los dos nulos: los
usuarios que ya existen quedan sin aceptación y la aceptarán una vez al entrar
(decidido con Agustín el 20 oct 2026), igual que las altas con Google. La
versión vigente es una constante del backend (terms_of_service.py). Solo SQL
plano: cabe en el guion del modo offline.

Revision ID: d6e8f0a2b4c6
Revises: c5f7a9b1d3e5
Create Date: 2026-10-20

"""

import sqlalchemy as sa
from alembic import op

revision = "d6e8f0a2b4c6"
down_revision = "c5f7a9b1d3e5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Añade las dos columnas, nulas, sin rellenar a nadie."""
    op.add_column(
        "users",
        sa.Column(
            "terms_accepted_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment=(
                "Cuándo aceptó la versión de terms_version (UTC): la primera vez, "
                "aceptarla otra vez no la cambia. NULL = nunca"
            ),
        ),
    )
    op.add_column(
        "users",
        sa.Column(
            "terms_version",
            sa.String(20),
            nullable=True,
            comment="La versión más reciente de los Términos que ha aceptado. NULL = nunca",
        ),
    )


def downgrade() -> None:
    """Quita las dos columnas."""
    op.drop_column("users", "terms_version")
    op.drop_column("users", "terms_accepted_at")
