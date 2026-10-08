"""Add tee_window_waits and waiting-list marks on places (BE #251)

Las listas de espera de las franjas de un Stableford o un Medal (decidido el 20
sep y el 8 oct 2026): una fila por jugador y franja, por orden de llegada. Y en
cada plaza, si la asignó la lista de espera y si el jugador ya lo vio en
«Requiere tu atención».

Revision ID: c9f1b3d5e7a8
Revises: b8e0a2c4d6f7
Create Date: 2026-10-08

"""

import sqlalchemy as sa
from alembic import op

revision = "c9f1b3d5e7a8"
down_revision = "b8e0a2c4d6f7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Las listas de espera y las dos marcas de la plaza."""
    op.create_table(
        "tee_window_waits",
        sa.Column("id", sa.CHAR(length=36), primary_key=True),
        sa.Column(
            "competition_id",
            sa.CHAR(length=36),
            sa.ForeignKey("competitions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "round_id",
            sa.CHAR(length=36),
            sa.ForeignKey("rounds.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            sa.CHAR(length=36),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("round_id", "user_id", name="uq_tee_window_waits_round_user"),
    )
    op.create_index("ix_tee_window_waits_competition_id", "tee_window_waits", ["competition_id"])
    op.add_column(
        "tee_window_places",
        sa.Column("from_waiting_list_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "tee_window_places",
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
    )
    # «Requiere tu atención», en cada carga del Dashboard: solo las asignadas sin ver
    op.create_index(
        "ix_tee_window_places_pending_ack",
        "tee_window_places",
        ["user_id"],
        postgresql_where=sa.text(
            "from_waiting_list_at IS NOT NULL AND acknowledged_at IS NULL"
        ),
    )


def downgrade() -> None:
    """Quita las listas y las marcas."""
    op.drop_index("ix_tee_window_places_pending_ack", table_name="tee_window_places")
    op.drop_column("tee_window_places", "acknowledged_at")
    op.drop_column("tee_window_places", "from_waiting_list_at")
    op.drop_index("ix_tee_window_waits_competition_id", table_name="tee_window_waits")
    op.drop_table("tee_window_waits")
