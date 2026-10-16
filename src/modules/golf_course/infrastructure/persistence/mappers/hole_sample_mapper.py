"""
Tabla de las muestras anónimas de hoyo (BE #532, reglas del 16 oct 2026).

Tabla:
- golf_course_hole_samples (como mucho tres filas por campo y hoyo)

No guarda quién mandó cada muestra: no hay columna de usuario. No se mapea la
entidad: el repositorio escribe y lee las filas a mano. Los codos van en JSONB
como `[[lat, lon], ...]`.
"""

from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    SmallInteger,
    Table,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID

from src.shared.infrastructure.persistence.sqlalchemy.base import metadata

from .golf_course_mapper import GolfCourseIdType

golf_course_hole_samples_table = Table(
    "golf_course_hole_samples",
    metadata,
    Column("id", UUID(as_uuid=True), primary_key=True),
    Column(
        "golf_course_id",
        GolfCourseIdType,
        ForeignKey("golf_courses.id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column("hole_number", SmallInteger, nullable=False),
    Column("tee_latitude", Float, nullable=False, comment="Salida"),
    Column("tee_longitude", Float, nullable=False),
    Column(
        "bends",
        JSONB,
        nullable=False,
        server_default=text("'[]'::jsonb"),
        comment="Codos de la línea de juego: [[lat, lon], ...]",
    ),
    Column("green_latitude", Float, nullable=False, comment="Centro del green"),
    Column("green_longitude", Float, nullable=False),
    Column("created_at", DateTime, nullable=False, comment="Cuándo llegó (UTC)"),
    CheckConstraint("hole_number BETWEEN 1 AND 18", name="ck_golf_course_hole_samples_hole_number"),
    CheckConstraint(
        "jsonb_typeof(bends) = 'array' AND jsonb_array_length(bends) <= 2",
        name="ck_golf_course_hole_samples_bends",
    ),
    comment="Muestras anónimas de los hoyos (las tres primeras por hoyo), sin autor",
)

# Contar las de un hoyo y leer las de un campo en orden de llegada
Index(
    "ix_golf_course_hole_samples_course_hole_created",
    golf_course_hole_samples_table.c.golf_course_id,
    golf_course_hole_samples_table.c.hole_number,
    golf_course_hole_samples_table.c.created_at,
)
