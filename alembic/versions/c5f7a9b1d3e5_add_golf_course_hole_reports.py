"""Add golf_course_hole_reports (entrega 7, 18 oct 2026)

Decidido con Agustín el 18 oct 2026: un jugador puede reportar un hoyo mal con
un motivo y la línea que propone. Como las muestras, sin quién lo mandó y de
cuándo solo el día; el orden de llegada lo da `seq`. Como mucho tres abiertos
por hoyo. Solo SQL plano: cabe en el guion del modo offline.

Revision ID: c5f7a9b1d3e5
Revises: b4e6a8c0d2f3
Create Date: 2026-10-18

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "c5f7a9b1d3e5"
down_revision = "b4e6a8c0d2f3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Crea la tabla de reportes de hoyo, vacía."""
    op.create_table(
        "golf_course_hole_reports",
        sa.Column(
            "id", postgresql.UUID(as_uuid=True), primary_key=True, comment="Lo genera el móvil"
        ),
        sa.Column(
            "seq",
            sa.BigInteger(),
            sa.Identity(always=True),
            nullable=False,
            comment="Orden de llegada: el primer reporte es el de menor seq",
        ),
        sa.Column(
            "golf_course_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("golf_courses.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("hole_number", sa.SmallInteger(), nullable=False),
        sa.Column(
            "reason", sa.String(20), nullable=False, comment="WRONG_HOLE, WRONG_LINE o HOLE_CHANGED"
        ),
        sa.Column("tee_latitude", sa.Float(), nullable=False, comment="Salida propuesta"),
        sa.Column("tee_longitude", sa.Float(), nullable=False),
        sa.Column(
            "bends",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
            comment="Codos de la línea propuesta: [[lat, lon], ...]",
        ),
        sa.Column(
            "green_latitude", sa.Float(), nullable=False, comment="Centro del green propuesto"
        ),
        sa.Column("green_longitude", sa.Float(), nullable=False),
        sa.Column(
            "received_on", sa.Date(), nullable=False, comment="Día (UTC) en que llegó, sin hora"
        ),
        sa.CheckConstraint(
            "hole_number BETWEEN 1 AND 18", name="ck_golf_course_hole_reports_hole_number"
        ),
        sa.CheckConstraint(
            "reason IN ('WRONG_HOLE', 'WRONG_LINE', 'HOLE_CHANGED')",
            name="ck_golf_course_hole_reports_reason",
        ),
        sa.CheckConstraint(
            "jsonb_typeof(bends) = 'array' AND jsonb_array_length(bends) <= 2",
            name="ck_golf_course_hole_reports_bends",
        ),
        comment="Reportes anónimos de hoyos mal (los tres primeros abiertos por hoyo), sin autor ni hora",
    )
    op.create_index(
        "ix_golf_course_hole_reports_course_hole_seq",
        "golf_course_hole_reports",
        ["golf_course_id", "hole_number", "seq"],
    )


def downgrade() -> None:
    """Quita la tabla y su índice."""
    op.drop_index(
        "ix_golf_course_hole_reports_course_hole_seq", table_name="golf_course_hole_reports"
    )
    op.drop_table("golf_course_hole_reports")
