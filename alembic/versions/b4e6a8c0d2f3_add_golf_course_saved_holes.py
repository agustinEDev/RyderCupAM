"""Add golf_course_saved_holes (BE #575, 17 oct 2026)

Decidido con Agustín el 17 oct 2026: una referencia por hoyo. El admin guarda,
a partir de las muestras, la línea de cada hoyo (salida, hasta dos codos y
centro del green), la que ven todos los jugadores; guardada, el hoyo deja de
recoger muestras. Una fila por campo y hoyo. Solo SQL plano: cabe en el guion
del modo offline.

Revision ID: b4e6a8c0d2f3
Revises: a3d5f7b9c1e2
Create Date: 2026-10-17

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "b4e6a8c0d2f3"
down_revision = "a3d5f7b9c1e2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Crea la tabla de líneas guardadas, vacía."""
    op.create_table(
        "golf_course_saved_holes",
        sa.Column(
            "golf_course_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("golf_courses.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("hole_number", sa.SmallInteger(), primary_key=True),
        sa.Column("tee_latitude", sa.Float(), nullable=False, comment="Salida de referencia"),
        sa.Column("tee_longitude", sa.Float(), nullable=False),
        sa.Column(
            "bends",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
            comment="Codos de la línea: [[lat, lon], ...]",
        ),
        sa.Column("green_latitude", sa.Float(), nullable=False, comment="Centro del green"),
        sa.Column("green_longitude", sa.Float(), nullable=False),
        sa.Column(
            "saved_by",
            sa.CHAR(36),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
            comment="Admin que la guardó",
        ),
        sa.Column("saved_at", sa.DateTime(), nullable=False, comment="Cuándo se guardó"),
        sa.CheckConstraint(
            "hole_number BETWEEN 1 AND 18", name="ck_golf_course_saved_holes_hole_number"
        ),
        sa.CheckConstraint(
            "jsonb_typeof(bends) = 'array' AND jsonb_array_length(bends) <= 2",
            name="ck_golf_course_saved_holes_bends",
        ),
        comment="La línea de referencia de cada hoyo, guardada por un admin",
    )


def downgrade() -> None:
    """Quita la tabla: los hoyos vuelven a recoger muestras."""
    op.drop_table("golf_course_saved_holes")
