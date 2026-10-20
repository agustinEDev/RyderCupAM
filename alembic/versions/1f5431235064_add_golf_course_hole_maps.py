"""Add golf_course_hole_maps (BE #532, 15 oct 2026)

El mapa de los hoyos de cada recorrido, decidido con Agustín el 15 oct 2026: una
fila por campo con los hoyos en JSONB (línea de juego de la salida al green,
green con delante/centro/fondo y contorno opcional, y el origen de cada posición
por la licencia ODbL de OpenStreetMap). Nace pendiente de revisión y solo lo ven
los jugadores cuando lo aprueba un admin. Tabla nueva y vacía: no toca datos.
Solo SQL plano: cabe en el guion del modo offline.

Revision ID: 1f5431235064
Revises: f2b4d6e8a0c1
Create Date: 2026-10-15

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "1f5431235064"
down_revision = "f2b4d6e8a0c1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """La tabla, sin filas."""
    op.create_table(
        "golf_course_hole_maps",
        sa.Column(
            "golf_course_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("golf_courses.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("holes", postgresql.JSONB(), nullable=False, comment="Hoyos del mapa (JSONB)"),
        sa.Column(
            "osm_reference",
            sa.String(40),
            nullable=False,
            comment="Contorno del campo en OSM: way/<id> o relation/<id>",
        ),
        sa.Column("imported_at", sa.DateTime(), nullable=False, comment="Cuándo se importó"),
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            comment="Revisión: PENDING_REVIEW, APPROVED o REJECTED",
        ),
        sa.Column(
            "reviewed_by",
            sa.CHAR(36),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
            comment="Admin que lo revisó",
        ),
        sa.Column("reviewed_at", sa.DateTime(), nullable=True, comment="Cuándo se revisó"),
        sa.Column("rejection_reason", sa.String(500), nullable=True, comment="Motivo del rechazo"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            "status IN ('PENDING_REVIEW', 'APPROVED', 'REJECTED')",
            name="ck_golf_course_hole_maps_status",
        ),
        sa.CheckConstraint(
            "(status = 'PENDING_REVIEW') = (reviewed_at IS NULL)",
            name="ck_golf_course_hole_maps_review_consistency",
        ),
        sa.CheckConstraint(
            "jsonb_typeof(holes) = 'array' AND jsonb_array_length(holes) > 0",
            name="ck_golf_course_hole_maps_has_holes",
        ),
        sa.CheckConstraint(
            "rejection_reason IS NULL OR status = 'REJECTED'",
            name="ck_golf_course_hole_maps_reason_only_if_rejected",
        ),
        comment="Mapa de los hoyos de cada recorrido (posiciones de OSM o propias)",
    )


def downgrade() -> None:
    """Quita la tabla."""
    op.drop_table("golf_course_hole_maps")
