"""
Tabla de las muestras anónimas de hoyo (BE #532, reglas del 16 oct 2026).

Tabla:
- golf_course_hole_samples (como mucho tres filas por campo y hoyo, de cualquier
  barra, y una solo green; BE #575)

No guarda quién mandó cada muestra (no hay columna de usuario), y de cuándo
llegó solo el día: el orden de llegada lo da `seq`, una identidad de
PostgreSQL. El id lo genera el móvil. No se mapea la entidad: el repositorio
escribe y lee las filas a mano. Los codos van en JSONB como `[[lat, lon], ...]`.
"""

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Column,
    Date,
    Enum as SQLEnum,
    Float,
    ForeignKey,
    Identity,
    Index,
    SmallInteger,
    Table,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID

from src.modules.golf_course.domain.value_objects.tee_color import TeeColor
from src.shared.infrastructure.persistence.sqlalchemy.base import metadata

from .golf_course_mapper import GenderType, GolfCourseIdType

golf_course_hole_samples_table = Table(
    "golf_course_hole_samples",
    metadata,
    Column("id", UUID(as_uuid=True), primary_key=True, comment="Lo genera el móvil"),
    Column(
        "seq",
        BigInteger,
        Identity(always=True),
        nullable=False,
        comment="Orden de llegada: la primera muestra es la de menor seq",
    ),
    Column(
        "golf_course_id",
        GolfCourseIdType,
        ForeignKey("golf_courses.id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column("hole_number", SmallInteger, nullable=False),
    # El mismo tipo que el color de golf_course_tees
    Column(
        "tee_color",
        SQLEnum(TeeColor, name="tee_color_enum"),
        nullable=False,
        comment="Color de la barra desde la que se jugó",
    ),
    Column(
        "tee_gender",
        GenderType,
        nullable=True,
        comment="Género de la barra (MALE, FEMALE, o NULL si no tiene)",
    ),
    # NULL en una muestra solo green (17 oct)
    Column("tee_latitude", Float, nullable=True, comment="Salida (NULL: solo green)"),
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
    Column("received_on", Date, nullable=False, comment="Día (UTC) en que llegó, sin hora"),
    CheckConstraint("hole_number BETWEEN 1 AND 18", name="ck_golf_course_hole_samples_hole_number"),
    CheckConstraint(
        "jsonb_typeof(bends) = 'array' AND jsonb_array_length(bends) <= 2",
        name="ck_golf_course_hole_samples_bends",
    ),
    CheckConstraint(
        "tee_gender IS NULL OR tee_gender IN ('MALE', 'FEMALE')",
        name="ck_golf_course_hole_samples_tee_gender",
    ),
    CheckConstraint(
        "(tee_latitude IS NULL AND tee_longitude IS NULL AND jsonb_array_length(bends) = 0)"
        " OR (tee_latitude IS NOT NULL AND tee_longitude IS NOT NULL)",
        name="ck_golf_course_hole_samples_green_only",
    ),
    comment="Muestras anónimas de los hoyos (las tres primeras por hoyo), sin autor ni hora",
)

# Contar las de un hoyo (su prefijo) y leer las de un campo en orden de llegada
Index(
    "ix_golf_course_hole_samples_course_hole_tee_seq",
    golf_course_hole_samples_table.c.golf_course_id,
    golf_course_hole_samples_table.c.hole_number,
    golf_course_hole_samples_table.c.tee_color,
    golf_course_hole_samples_table.c.tee_gender,
    golf_course_hole_samples_table.c.seq,
)
