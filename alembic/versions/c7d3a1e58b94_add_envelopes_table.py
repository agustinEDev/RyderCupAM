"""Add envelopes table (FE #655)

El sobre de cada capitan para una sesion: una lista ORDENADA de los suyos, que
se cruza con la del rival por posicion. Las filas van como JSONB en la misma
fila del sobre porque el ORDEN es el dato; una tabla aparte obligaria a ordenar
por una columna que no aporta nada mas.

Revision ID: c7d3a1e58b94
Revises: f1a4c7d29b63
Create Date: 2026-09-23

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers, used by Alembic.
revision = "c7d3a1e58b94"
down_revision = "f1a4c7d29b63"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Crea la tabla de sobres."""
    op.create_table(
        "envelopes",
        sa.Column("id", sa.CHAR(36), primary_key=True),
        sa.Column(
            "competition_id",
            sa.CHAR(36),
            sa.ForeignKey("competitions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "round_id",
            sa.CHAR(36),
            sa.ForeignKey("rounds.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("team", sa.String(1), nullable=False),
        sa.Column("match_format", sa.String(20), nullable=False),
        sa.Column("entries", JSONB, nullable=False),
        sa.Column("submitted_at", sa.DateTime, nullable=True),
        # SET NULL: si el capitan se borra, el sobre sigue valiendo. Quien lo
        # entrego es auditoria, no lo que lo hace valido
        sa.Column(
            "submitted_by",
            sa.CHAR(36),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("automatic", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("revealed", sa.Boolean, nullable=False, server_default=sa.false()),
        # Uno por equipo y sesion: dos serian dos listas a la vez para el mismo
        # cruce, y nadie sabria cual manda
        sa.UniqueConstraint("round_id", "team", name="uq_envelopes_round_team"),
    )


def downgrade() -> None:
    """Elimina la tabla de sobres."""
    op.drop_table("envelopes")
