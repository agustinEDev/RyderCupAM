"""
Tabla de los reportes de hoyo (entrega 7, Agustín, 18 oct 2026).

Tabla:
- golf_course_hole_reports (como mucho tres filas por campo y hoyo)

No guarda quién mandó cada reporte (no hay columna de usuario), y de cuándo
llegó solo el día: el orden de llegada lo da `seq`, una identidad de
PostgreSQL. El id lo genera el móvil. No se mapea la entidad: el repositorio
escribe y lee las filas a mano. Los codos van en JSONB como `[[lat, lon], ...]`.
"""

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Column,
    Date,
    Float,
    ForeignKey,
    Identity,
    Index,
    SmallInteger,
    String,
    Table,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID

from src.shared.infrastructure.persistence.sqlalchemy.base import metadata

from .golf_course_mapper import GolfCourseIdType

golf_course_hole_reports_table = Table(
    "golf_course_hole_reports",
    metadata,
    Column("id", UUID(as_uuid=True), primary_key=True, comment="Lo genera el móvil"),
    Column(
        "seq",
        BigInteger,
        Identity(always=True),
        nullable=False,
        comment="Orden de llegada: el primer reporte es el de menor seq",
    ),
    Column(
        "golf_course_id",
        GolfCourseIdType,
        ForeignKey("golf_courses.id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column("hole_number", SmallInteger, nullable=False),
    Column(
        "reason",
        String(20),
        nullable=False,
        comment="WRONG_HOLE, WRONG_LINE o HOLE_CHANGED",
    ),
    Column("tee_latitude", Float, nullable=False, comment="Salida propuesta"),
    Column("tee_longitude", Float, nullable=False),
    Column(
        "bends",
        JSONB,
        nullable=False,
        server_default=text("'[]'::jsonb"),
        comment="Codos de la línea propuesta: [[lat, lon], ...]",
    ),
    Column("green_latitude", Float, nullable=False, comment="Centro del green propuesto"),
    Column("green_longitude", Float, nullable=False),
    Column("received_on", Date, nullable=False, comment="Día (UTC) en que llegó, sin hora"),
    CheckConstraint("hole_number BETWEEN 1 AND 18", name="ck_golf_course_hole_reports_hole_number"),
    CheckConstraint(
        "reason IN ('WRONG_HOLE', 'WRONG_LINE', 'HOLE_CHANGED')",
        name="ck_golf_course_hole_reports_reason",
    ),
    CheckConstraint(
        "jsonb_typeof(bends) = 'array' AND jsonb_array_length(bends) <= 2",
        name="ck_golf_course_hole_reports_bends",
    ),
    comment="Reportes anónimos de hoyos mal (los tres primeros abiertos por hoyo), sin autor ni hora",
)

# Contar los de un hoyo y leer los de un campo en orden de llegada
Index(
    "ix_golf_course_hole_reports_course_hole_seq",
    golf_course_hole_reports_table.c.golf_course_id,
    golf_course_hole_reports_table.c.hole_number,
    golf_course_hole_reports_table.c.seq,
)
