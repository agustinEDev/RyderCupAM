"""Add reveal_when_both_ready to envelopes (FE #655)

El capitan puede pedir, al entregar, que los sobres se abran en cuanto esten
los dos, sin esperar a la hora. Hacen falta LOS DOS para que valga: con uno
solo se espera, porque el otro tiene derecho a su plazo.

Revision ID: d8e2f4a19c73
Revises: c7d3a1e58b94
Create Date: 2026-09-23

"""

import sqlalchemy as sa
from alembic import op

revision = "d8e2f4a19c73"
down_revision = "c7d3a1e58b94"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Anade la casilla al sobre."""
    op.add_column(
        "envelopes",
        sa.Column(
            "reveal_when_both_ready",
            sa.Boolean,
            nullable=False,
            server_default=sa.false(),
        ),
    )


def downgrade() -> None:
    """Quita la casilla."""
    op.drop_column("envelopes", "reveal_when_both_ready")
