"""document team_assignment TypeDecorator adoption in ORM mapper

Revision ID: d4f6a8b2c9e3
Revises: c3d5e7f9a1b2
Create Date: 2026-02-15 23:00:00.000000

Records the switch from plain String(20) to TeamAssignmentModeDecorator
in the SQLAlchemy ORM mapper for the competitions.team_assignment column.
The underlying database type remains String(20) — this migration exists
to prevent Alembic autogenerate from detecting a spurious ALTER.
"""

from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "d4f6a8b2c9e3"
down_revision: str | None = "c3d5e7f9a1b2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # No-op: the underlying column type is still String(20).
    # This migration documents the ORM-level switch from plain String(20)
    # to TeamAssignmentModeDecorator (which wraps String(20)) for the
    # competitions.team_assignment column, ensuring Alembic's history
    # stays in sync with the mapper definition.
    pass


def downgrade() -> None:
    # No-op: reverting the TypeDecorator change has no DB-level effect.
    pass
