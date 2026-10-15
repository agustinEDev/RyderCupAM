"""
Tabla de las marcas de hoyo de los jugadores (BE #532, PR C).

Tabla:
- golf_course_hole_marks (una fila por campo, jugador y hoyo)

No se mapea la entidad: el repositorio escribe con un upsert de PostgreSQL
(volver a marcar sustituye la marca, y dos envíos a la vez no chocan en la
clave) y lee las filas a mano. Los codos van en JSONB como `[[lat, lon], ...]`.
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

golf_course_hole_marks_table = Table(
    "golf_course_hole_marks",
    metadata,
    Column(
        "golf_course_id",
        GolfCourseIdType,
        ForeignKey("golf_courses.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    # CASCADE: al borrar la cuenta se van sus marcas
    Column(
        "user_id",
        UserIdType,
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column("hole_number", SmallInteger, primary_key=True),
    Column("tee_latitude", Float, nullable=True, comment="Null si el hoyo ya tenía salida"),
    Column("tee_longitude", Float, nullable=True),
    Column(
        "bends",
        JSONB,
        nullable=False,
        server_default=text("'[]'::jsonb"),
        comment="Codos de la línea de juego: [[lat, lon], ...]",
    ),
    Column("green_latitude", Float, nullable=False, comment="Centro del green"),
    Column("green_longitude", Float, nullable=False),
    Column("created_at", DateTime, nullable=False, comment="Primera vez que lo marcó"),
    Column("updated_at", DateTime, nullable=False, comment="Última vez que lo marcó"),
    CheckConstraint("hole_number BETWEEN 1 AND 18", name="ck_golf_course_hole_marks_hole_number"),
    CheckConstraint(
        "(tee_latitude IS NULL) = (tee_longitude IS NULL)",
        name="ck_golf_course_hole_marks_tee_complete",
    ),
    # Hasta dos codos, y solo con salida propia
    CheckConstraint(
        "jsonb_typeof(bends) = 'array' AND jsonb_array_length(bends) <= 2 "
        "AND (tee_latitude IS NOT NULL OR jsonb_array_length(bends) = 0)",
        name="ck_golf_course_hole_marks_bends",
    ),
    comment="Hoyos marcados por los jugadores, pendientes de pasar al mapa",
)
