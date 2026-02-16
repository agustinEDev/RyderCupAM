"""
SQLAlchemy Mapper for GolfCourse aggregate.

Tablas:
- golf_courses (agregado raíz)
- golf_course_tees (value object collection)
- golf_course_holes (value object collection)
"""

import uuid
from datetime import datetime
from typing import Any

import sqlalchemy.types
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    Enum as SQLEnum,
    Float,
    ForeignKey,
    Integer,
    String,
    Table,
    UniqueConstraint,
    event,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import column_property, relationship
from sqlalchemy.types import CHAR

from src.modules.golf_course.domain.entities.golf_course import GolfCourse
from src.modules.golf_course.domain.entities.hole import Hole
from src.modules.golf_course.domain.entities.tee import Tee
from src.modules.golf_course.domain.value_objects.approval_status import ApprovalStatus
from src.modules.golf_course.domain.value_objects.course_type import CourseType
from src.modules.golf_course.domain.value_objects.golf_course_id import GolfCourseId
from src.modules.golf_course.domain.value_objects.tee_category import TeeCategory
from src.modules.user.domain.value_objects.user_id import UserId
from src.shared.domain.value_objects.country_code import CountryCode
from src.shared.domain.value_objects.gender import Gender
from src.shared.infrastructure.persistence.sqlalchemy.base import mapper_registry, metadata

# ============================================================================
# TypeDecorators for Value Objects (MUST be before tables)
# ============================================================================


class GolfCourseIdType(sqlalchemy.types.TypeDecorator[GolfCourseId]):
    """TypeDecorator para GolfCourseId Value Object."""

    impl = UUID(as_uuid=True)
    cache_ok = True

    def process_bind_param(self, value: GolfCourseId | None, dialect: Any) -> uuid.UUID | None:
        """Convierte GolfCourseId → UUID para persistencia."""
        if value is None:
            return None
        return value.value  # value.value ya es uuid.UUID object

    def process_result_value(self, value: uuid.UUID | None, dialect: Any) -> GolfCourseId | None:
        """Convierte UUID → GolfCourseId al hidratar."""
        if value is None:
            return None
        return GolfCourseId(value)  # GolfCourseId acepta uuid.UUID object


class CountryCodeType(sqlalchemy.types.TypeDecorator[CountryCode]):
    """TypeDecorator para CountryCode Value Object."""

    impl = String(2)
    cache_ok = True

    def process_bind_param(self, value: CountryCode | None, dialect: Any) -> str | None:
        """Convierte CountryCode → str para persistencia."""
        if value is None:
            return None
        return value.value

    def process_result_value(self, value: str | None, dialect: Any) -> CountryCode | None:
        """Convierte str → CountryCode al hidratar."""
        if value is None:
            return None
        return CountryCode(value)


class UserIdType(sqlalchemy.types.TypeDecorator[UserId]):
    """TypeDecorator para UserId Value Object (compatible con users.id CHAR(36))."""

    impl = CHAR(36)
    cache_ok = True

    def process_bind_param(self, value: UserId | None, dialect: Any) -> str | None:
        """Convierte UserId → str para persistencia."""
        if value is None:
            return None
        return str(value.value)

    def process_result_value(self, value: str | None, dialect: Any) -> UserId | None:
        """Convierte str → UserId al hidratar."""
        if value is None:
            return None
        return UserId(uuid.UUID(value))


class GenderType(sqlalchemy.types.TypeDecorator[Gender]):
    """TypeDecorator para Gender Value Object (nullable)."""

    impl = String(10)
    cache_ok = True

    def process_bind_param(self, value: Gender | None, dialect: Any) -> str | None:
        if value is None:
            return None
        return value.value

    def process_result_value(self, value: str | None, dialect: Any) -> Gender | None:
        if value is None:
            return None
        return Gender(value)


# ============================================================================
# Tables
# ============================================================================

golf_courses_table = Table(
    "golf_courses",
    metadata,
    Column("id", GolfCourseIdType, primary_key=True),
    Column("name", String(200), nullable=False, comment="Nombre del campo de golf"),
    Column("country_code", CountryCodeType, ForeignKey("countries.code"), nullable=False),
    Column(
        "course_type",
        SQLEnum(CourseType, name="course_type_enum", create_type=False),
        nullable=False,
        comment="Tipo de campo (STANDARD_18, etc.)",
    ),
    Column("creator_id", UserIdType, ForeignKey("users.id"), nullable=False),
    Column(
        "approval_status",
        SQLEnum(ApprovalStatus, name="approval_status_enum", create_type=False),
        nullable=False,
        default=ApprovalStatus.PENDING_APPROVAL,
        comment="Estado de aprobación (PENDING_APPROVAL, APPROVED, REJECTED)",
    ),
    Column(
        "rejection_reason",
        String(500),
        nullable=True,
        comment="Razón de rechazo (solo si REJECTED)",
    ),
    Column("created_at", DateTime, nullable=False, default=datetime.utcnow),
    Column(
        "updated_at", DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    ),
    Column(
        "original_golf_course_id",
        GolfCourseIdType,
        ForeignKey("golf_courses.id", ondelete="CASCADE"),
        nullable=True,
        comment="If not NULL, this is a clone/update proposal of the original golf course",
    ),
    Column(
        "is_pending_update",
        Boolean,
        nullable=False,
        default=False,
        comment="TRUE if this golf course has a pending update clone",
    ),
    CheckConstraint("LENGTH(name) >= 3", name="ck_golf_courses_name_min_length"),
    CheckConstraint(
        "(approval_status != 'REJECTED') OR (rejection_reason IS NOT NULL)",
        name="ck_golf_courses_rejection_reason_required",
    ),
    comment="Campos de golf con workflow de aprobación Admin",
)

golf_course_tees_table = Table(
    "golf_course_tees",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column(
        "golf_course_id",
        GolfCourseIdType,
        ForeignKey("golf_courses.id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column(
        "tee_category",
        SQLEnum(TeeCategory, name="tee_category_enum", create_type=False),
        nullable=False,
        comment="Categoría normalizada WHS (CHAMPIONSHIP, AMATEUR, SENIOR, FORWARD, JUNIOR)",
    ),
    Column(
        "tee_gender",
        GenderType,
        nullable=True,
        comment="Género del tee (MALE, FEMALE, o NULL para gender-neutral)",
    ),
    Column(
        "identifier",
        String(50),
        nullable=False,
        comment="Identificador libre del campo (Amarillo, Oro, 1, etc.)",
    ),
    Column(
        "course_rating",
        Float,
        nullable=False,
        comment="Course Rating WHS (50.0-90.0)",
    ),
    Column(
        "slope_rating",
        Integer,
        nullable=False,
        comment="Slope Rating WHS (55-155)",
    ),
    CheckConstraint(
        "course_rating >= 50.0 AND course_rating <= 90.0", name="ck_tees_course_rating_range"
    ),
    CheckConstraint(
        "slope_rating >= 55 AND slope_rating <= 155", name="ck_tees_slope_rating_range"
    ),
    # Unique index on (golf_course_id, tee_category, COALESCE(tee_gender, 'NONE'))
    # created in Alembic migration c3d5e7f9a1b2 as functional index
    comment="Tees (salidas) de campos de golf con ratings WHS",
)

golf_course_holes_table = Table(
    "golf_course_holes",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column(
        "golf_course_id",
        GolfCourseIdType,
        ForeignKey("golf_courses.id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column("hole_number", Integer, nullable=False, comment="Número de hoyo (1-18)"),
    Column("par", Integer, nullable=False, comment="Par del hoyo (3-5)"),
    Column("stroke_index", Integer, nullable=False, comment="Índice de dificultad (1-18)"),
    CheckConstraint("hole_number >= 1 AND hole_number <= 18", name="ck_holes_number_range"),
    CheckConstraint("par >= 3 AND par <= 5", name="ck_holes_par_range"),
    CheckConstraint("stroke_index >= 1 AND stroke_index <= 18", name="ck_holes_stroke_index_range"),
    UniqueConstraint("golf_course_id", "hole_number", name="uq_golf_course_holes_number"),
    UniqueConstraint("golf_course_id", "stroke_index", name="uq_golf_course_holes_stroke_index"),
    comment="Hoyos de campos de golf (18 por campo)",
)

# ============================================================================
# Imperative Mapping
# ============================================================================


def start_golf_course_mappers():
    """
    Inicia el mapeo entre entidades de Golf Course y tablas de BD.

    Es idempotente - puede llamarse múltiples veces sin problemas.

    Mapea:
    - GolfCourse entity → golf_courses table
    - Tee value object → golf_course_tees table
    - Hole value object → golf_course_holes table
    """
    # Mapear Tee (value object collection)
    if Tee not in mapper_registry.mappers:
        mapper_registry.map_imperatively(
            Tee,
            golf_course_tees_table,
            properties={
                # Map database column tee_category to entity attribute category
                "category": golf_course_tees_table.c.tee_category,
                # Map database column tee_gender to entity attribute gender
                "gender": golf_course_tees_table.c.tee_gender,
            },
        )

    # Mapear Hole (value object collection)
    if Hole not in mapper_registry.mappers:
        mapper_registry.map_imperatively(
            Hole,
            golf_course_holes_table,
            properties={
                # Map database column hole_number to entity attribute number
                "number": golf_course_holes_table.c.hole_number,
            },
        )

    # Mapear GolfCourse (aggregate root)
    if GolfCourse not in mapper_registry.mappers:
        mapper_registry.map_imperatively(
            GolfCourse,
            golf_courses_table,
            properties={
                # Value Objects mapping (TypeDecorators en tabla)
                "_id": column_property(golf_courses_table.c.id),
                "_country_code": column_property(golf_courses_table.c.country_code),
                "_creator_id": column_property(golf_courses_table.c.creator_id),
                "_original_golf_course_id": column_property(
                    golf_courses_table.c.original_golf_course_id
                ),
                # Scalar attributes mapping
                "_name": column_property(golf_courses_table.c.name),
                "_course_type": column_property(golf_courses_table.c.course_type),
                "_approval_status": column_property(golf_courses_table.c.approval_status),
                "_rejection_reason": column_property(golf_courses_table.c.rejection_reason),
                "_created_at": column_property(golf_courses_table.c.created_at),
                "_updated_at": column_property(golf_courses_table.c.updated_at),
                "_is_pending_update": column_property(golf_courses_table.c.is_pending_update),
                # One-to-many relationships with tees and holes
                "_tees": relationship(
                    Tee,
                    cascade="all, delete-orphan",
                    lazy="joined",  # Eager loading
                    # No order_by needed - tees don't have a meaningful order
                ),
                "_holes": relationship(
                    Hole,
                    cascade="all, delete-orphan",
                    lazy="joined",  # Eager loading
                    order_by=golf_course_holes_table.c.hole_number,  # DB column name
                ),
            },
        )

        # Event listener: initialize _domain_events when SQLAlchemy loads from DB
        # (replaces @reconstructor that was previously in the domain entity)
        @event.listens_for(GolfCourse, "load")
        def _init_golf_course_domain_events(target, _context):
            if not hasattr(target, "_domain_events"):
                target._domain_events = []
