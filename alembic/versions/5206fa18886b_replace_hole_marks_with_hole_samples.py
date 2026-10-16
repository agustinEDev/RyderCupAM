"""Replace golf_course_hole_marks with golf_course_hole_samples (BE #532, 16 oct 2026)

Las marcas por jugador (7c2e9a4b1d30) se sustituyen por muestras anónimas,
decidido con Agustín el 16 oct 2026: por hoyo y barra (color y género) se
guardan solo las tres primeras muestras válidas que llegan (salida, hasta dos
codos y centro del green), sin quién las mandó y, de cuándo, solo el día: el
orden de llegada lo da `seq`. El id lo genera el móvil (un reenvío cuenta una
vez). Las marcas no llegaron a producción: la tabla vieja se borra sin pasar
datos. Solo SQL plano: cabe en el guion del modo offline.

Revision ID: 5206fa18886b
Revises: 7c2e9a4b1d30
Create Date: 2026-10-16

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "5206fa18886b"
down_revision = "7c2e9a4b1d30"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Quita las marcas y crea la tabla de muestras, vacía."""
    op.drop_index("ix_golf_course_hole_marks_user_id", table_name="golf_course_hole_marks")
    op.drop_table("golf_course_hole_marks")

    op.create_table(
        "golf_course_hole_samples",
        sa.Column(
            "id", postgresql.UUID(as_uuid=True), primary_key=True, comment="Lo genera el móvil"
        ),
        sa.Column(
            "seq",
            sa.BigInteger(),
            sa.Identity(always=True),
            nullable=False,
            comment="Orden de llegada: la primera muestra es la de menor seq",
        ),
        sa.Column(
            "golf_course_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("golf_courses.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("hole_number", sa.SmallInteger(), nullable=False),
        # El tipo del color de golf_course_tees, que ya existe
        sa.Column(
            "tee_color",
            postgresql.ENUM(name="tee_color_enum", create_type=False),
            nullable=False,
            comment="Color de la barra desde la que se jugó",
        ),
        sa.Column(
            "tee_gender",
            sa.String(10),
            nullable=True,
            comment="Género de la barra (MALE, FEMALE, o NULL si no tiene)",
        ),
        sa.Column("tee_latitude", sa.Float(), nullable=False, comment="Salida"),
        sa.Column("tee_longitude", sa.Float(), nullable=False),
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
            "received_on", sa.Date(), nullable=False, comment="Día (UTC) en que llegó, sin hora"
        ),
        sa.CheckConstraint(
            "hole_number BETWEEN 1 AND 18", name="ck_golf_course_hole_samples_hole_number"
        ),
        sa.CheckConstraint(
            "jsonb_typeof(bends) = 'array' AND jsonb_array_length(bends) <= 2",
            name="ck_golf_course_hole_samples_bends",
        ),
        sa.CheckConstraint(
            "tee_gender IS NULL OR tee_gender IN ('MALE', 'FEMALE')",
            name="ck_golf_course_hole_samples_tee_gender",
        ),
        comment="Muestras anónimas de los hoyos (las tres primeras por barra), sin autor ni hora",
    )
    # Contar las de una barra y leer las de un campo en orden de llegada. Tabla
    # recién creada y vacía: no hace falta CONCURRENTLY
    op.create_index(
        "ix_golf_course_hole_samples_course_hole_tee_seq",
        "golf_course_hole_samples",
        ["golf_course_id", "hole_number", "tee_color", "tee_gender", "seq"],
    )


def downgrade() -> None:
    """Quita las muestras (se pierden) y vuelve a crear la tabla de marcas, vacía."""
    op.drop_table("golf_course_hole_samples")

    # Copia de la definición de 7c2e9a4b1d30
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
        sa.Column("created_at", sa.DateTime(), nullable=False, comment="Primera vez que lo marcó"),
        sa.Column("updated_at", sa.DateTime(), nullable=False, comment="Última vez que lo marcó"),
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
    op.create_index("ix_golf_course_hole_marks_user_id", "golf_course_hole_marks", ["user_id"])
