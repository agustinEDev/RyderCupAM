"""Add hidden_by_participant_ids to quick_matches

Revision ID: 2a33bf8e43ff
Revises: f3a9c2e7b1d4
Create Date: 2026-08-02 12:00:00.000000

"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision = "2a33bf8e43ff"
down_revision = "f3a9c2e7b1d4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Lista (JSONB) de ParticipantId que han ocultado la partida de su propio
    # historial — reemplaza el borrado fisico originalmente planteado en #127:
    # un participante deja de verla en /quick-matches/me sin afectar al resto
    # ni borrar ningun dato.
    op.add_column(
        "quick_matches",
        sa.Column(
            "hidden_by_participant_ids",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="[]",
        ),
    )


def downgrade() -> None:
    op.drop_column("quick_matches", "hidden_by_participant_ids")
