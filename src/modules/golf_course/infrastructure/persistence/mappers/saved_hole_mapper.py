"""
Tabla de las líneas que el admin guarda de cada hoyo (BE #575, 17 oct 2026).

Tabla:
- golf_course_saved_holes (una fila por campo y hoyo)

Como las muestras, no se mapea la entidad: el repositorio escribe y lee las
filas a mano. Los codos van en JSONB como `[[lat, lon], ...]`.
"""

from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    Float,
    ForeignKey,
    SmallInteger,
    Table,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB

from src.shared.infrastructure.persistence.sqlalchemy.base import metadata

from .golf_course_mapper import GolfCourseIdType, UserIdType

golf_course_saved_holes_table = Table(
    "golf_course_saved_holes",
    metadata,
    Column(
        "golf_course_id",
        GolfCourseIdType,
        ForeignKey("golf_courses.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column("hole_number", SmallInteger, primary_key=True),
    Column("tee_latitude", Float, nullable=False, comment="Salida de referencia"),
    Column("tee_longitude", Float, nullable=False),
    Column(
        "bends",
        JSONB,
        nullable=False,
        server_default=text("'[]'::jsonb"),
        comment="Codos de la línea: [[lat, lon], ...]",
    ),
    Column("green_latitude", Float, nullable=False, comment="Centro del green"),
    Column("green_longitude", Float, nullable=False),
    # SET NULL: borrar al admin que la guardó no quita la línea
    Column(
        "saved_by",
        UserIdType,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="Admin que la guardó",
    ),
    Column("saved_at", DateTime, nullable=False, comment="Cuándo se guardó"),
    CheckConstraint("hole_number BETWEEN 1 AND 18", name="ck_golf_course_saved_holes_hole_number"),
    CheckConstraint(
        "jsonb_typeof(bends) = 'array' AND jsonb_array_length(bends) <= 2",
        name="ck_golf_course_saved_holes_bends",
    ),
    comment="La línea de referencia de cada hoyo, guardada por un admin",
)
