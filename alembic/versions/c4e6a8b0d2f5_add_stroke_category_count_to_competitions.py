"""Add equal categories count to competitions (BE #251)

Decidido con Agustín el 10 oct 2026: además de escribir los límites de las
categorías, el organizador de un Stableford o un Medal puede pedir N categorías
iguales, y los límites salen al cerrar las inscripciones con los hándicaps
fijados. La columna guarda cuántas se pidieron; vacía, los límites son a mano,
que es lo que son todas las que ya existen. Sin relleno: cabe en el guion del
modo offline (`alembic upgrade head --sql`).

Revision ID: c4e6a8b0d2f5
Revises: a3c5e7b9d1f3
Create Date: 2026-10-10

"""

import sqlalchemy as sa
from alembic import op

revision = "c4e6a8b0d2f5"
down_revision = "a3c5e7b9d1f3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Añade cuántas categorías iguales se piden; vacía es «límites a mano»."""
    op.add_column(
        "competitions",
        sa.Column("stroke_category_count", sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    """Quita el número de categorías iguales."""
    op.drop_column("competitions", "stroke_category_count")
