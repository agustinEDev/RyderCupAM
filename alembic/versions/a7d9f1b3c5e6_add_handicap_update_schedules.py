"""Add handicap_update_schedules (BE #251)

La actualización de hándicaps que deja programada el organizador (decidido el
7 oct 2026): una por competición, editable y cancelable hasta su hora. La lanza
el vigilante; si a esa hora la ventana está cerrada, no se lanza y se avisa.

Revision ID: a7d9f1b3c5e6
Revises: f6c8e0a2b4d5
Create Date: 2026-10-07

"""

import sqlalchemy as sa
from alembic import op

revision = "a7d9f1b3c5e6"
down_revision = "f6c8e0a2b4d5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Una fila por competición con su hora."""
    op.create_table(
        "handicap_update_schedules",
        sa.Column(
            "competition_id",
            sa.CHAR(length=36),
            sa.ForeignKey("competitions.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("run_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_handicap_update_schedules_run_at", "handicap_update_schedules", ["run_at"]
    )


def downgrade() -> None:
    """Quita las programadas."""
    op.drop_index("ix_handicap_update_schedules_run_at", table_name="handicap_update_schedules")
    op.drop_table("handicap_update_schedules")
