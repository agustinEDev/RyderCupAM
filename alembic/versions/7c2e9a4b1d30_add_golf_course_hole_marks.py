"""Add golf_course_hole_marks (BE #532, PR C, 15 oct 2026)

Los hoyos que marcan los jugadores en el mapa, decidido con Agustín el 15 oct
2026: en un hoyo sin datos tocan la salida y el centro del green (y arrastran
hasta dos codos); si el hoyo ya tiene salida, solo el green. Una fila por campo,
jugador y hoyo: volver a marcar la sustituye. Las ve el jugador al momento y
los demás cuando un admin las apruebe (PR B). Tabla nueva y vacía: no toca
datos. Solo SQL plano: cabe en el guion del modo offline.

Revision ID: 7c2e9a4b1d30
Revises: 1f5431235064
Create Date: 2026-10-15

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "7c2e9a4b1d30"
down_revision = "1f5431235064"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """La tabla, sin filas."""
    op.create_table(
        "golf_course_hole_marks",
        sa.Column(
            "golf_course_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("golf_courses.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "user_id",
            sa.CHAR(36),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("hole_number", sa.SmallInteger(), primary_key=True),
        sa.Column(
            "tee_latitude", sa.Float(), nullable=True, comment="Null si el hoyo ya tenía salida"
        ),
        sa.Column("tee_longitude", sa.Float(), nullable=True),
        sa.Column(
            "bends",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
            comment="Codos de la línea de juego: [[lat, lon], ...]",
        ),
        sa.Column("green_latitude", sa.Float(), nullable=False, comment="Centro del green"),
        sa.Column("green_longitude", sa.Float(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(), nullable=False, comment="Primera vez que lo marcó"
        ),
        sa.Column(
            "updated_at", sa.DateTime(), nullable=False, comment="Última vez que lo marcó"
        ),
        sa.CheckConstraint(
            "hole_number BETWEEN 1 AND 18", name="ck_golf_course_hole_marks_hole_number"
        ),
        sa.CheckConstraint(
            "(tee_latitude IS NULL) = (tee_longitude IS NULL)",
            name="ck_golf_course_hole_marks_tee_complete",
        ),
        sa.CheckConstraint(
            "jsonb_typeof(bends) = 'array' AND jsonb_array_length(bends) <= 2 "
            "AND (tee_latitude IS NOT NULL OR jsonb_array_length(bends) = 0)",
            name="ck_golf_course_hole_marks_bends",
        ),
        comment="Hoyos marcados por los jugadores, pendientes de pasar al mapa",
    )
    # La clave empieza por el campo: sin esto, borrar una cuenta recorrería la
    # tabla entera. Tabla recién creada y vacía: no hace falta CONCURRENTLY
    op.create_index("ix_golf_course_hole_marks_user_id", "golf_course_hole_marks", ["user_id"])


def downgrade() -> None:
    """Quita la tabla (y con ella su índice)."""
    op.drop_table("golf_course_hole_marks")
