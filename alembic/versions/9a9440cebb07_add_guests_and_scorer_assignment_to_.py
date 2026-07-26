"""Add guests and scorer assignment to quick_match

Revision ID: 9a9440cebb07
Revises: a91cc79ba087
Create Date: 2026-07-26 17:00:00.000000

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "9a9440cebb07"
down_revision = "a91cc79ba087"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # quick_matches: nueva columna scorer_ids (JSONB, lista de participant_id)
    op.add_column(
        "quick_matches",
        sa.Column(
            "scorer_ids",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="[]",
        ),
    )

    # quick_match_hole_scores: player_user_id (CHAR(36), FK a users) ->
    # participant_id (UUID, sin FK: puede ser un invitado sin cuenta)
    op.drop_constraint(
        "uq_quick_match_hole_player", "quick_match_hole_scores", type_="unique"
    )
    op.drop_constraint(
        "quick_match_hole_scores_player_user_id_fkey",
        "quick_match_hole_scores",
        type_="foreignkey",
    )
    op.execute(
        "ALTER TABLE quick_match_hole_scores "
        "RENAME COLUMN player_user_id TO participant_id"
    )
    op.execute(
        "ALTER TABLE quick_match_hole_scores "
        "ALTER COLUMN participant_id TYPE uuid USING participant_id::uuid"
    )

    # recorded_by_participant_id: quien registro el score (el propio jugador o
    # el anotador que lo hizo por delegacion). Backfill = participant_id.
    op.add_column(
        "quick_match_hole_scores",
        sa.Column("recorded_by_participant_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.execute(
        "UPDATE quick_match_hole_scores SET recorded_by_participant_id = participant_id"
    )
    op.alter_column("quick_match_hole_scores", "recorded_by_participant_id", nullable=False)

    op.create_unique_constraint(
        "uq_quick_match_hole_participant",
        "quick_match_hole_scores",
        ["quick_match_id", "hole_number", "participant_id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_quick_match_hole_participant", "quick_match_hole_scores", type_="unique"
    )
    op.drop_column("quick_match_hole_scores", "recorded_by_participant_id")

    op.execute(
        "ALTER TABLE quick_match_hole_scores "
        "ALTER COLUMN participant_id TYPE CHAR(36) USING participant_id::text"
    )
    op.execute(
        "ALTER TABLE quick_match_hole_scores "
        "RENAME COLUMN participant_id TO player_user_id"
    )
    op.create_foreign_key(
        "quick_match_hole_scores_player_user_id_fkey",
        "quick_match_hole_scores",
        "users",
        ["player_user_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_unique_constraint(
        "uq_quick_match_hole_player",
        "quick_match_hole_scores",
        ["quick_match_id", "hole_number", "player_user_id"],
    )

    op.drop_column("quick_matches", "scorer_ids")
