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
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import registry, relationship

from src.modules.golf_course.domain.entities.golf_course import GolfCourse
from src.modules.golf_course.domain.entities.hole import Hole
from src.modules.golf_course.domain.entities.tee import Tee
from src.modules.golf_course.domain.value_objects.approval_status import ApprovalStatus
from src.modules.golf_course.domain.value_objects.course_type import CourseType
from src.modules.golf_course.domain.value_objects.golf_course_id import GolfCourseId
from src.modules.golf_course.domain.value_objects.tee_category import TeeCategory
from src.modules.user.domain.value_objects.user_id import UserId
from src.shared.domain.value_objects.country_code import CountryCode

# ============================================================================
# Mapper Registry
# ============================================================================

mapper_registry = registry()

# ============================================================================
# Tables
# ============================================================================

golf_courses_table = Table(
    "golf_courses",
    mapper_registry.metadata,
    Column("id", UUID(as_uuid=True), primary_key=True),
    Column("name", String(200), nullable=False, comment="Nombre del campo de golf"),
    Column("country_code", String(2), ForeignKey("countries.code"), nullable=False),
    Column(
        "course_type",
        SQLEnum(CourseType, name="course_type_enum", create_type=False),
        nullable=False,
        comment="Tipo de campo (STANDARD_18, etc.)",
    ),
    Column("creator_id", UUID(as_uuid=True), ForeignKey("users.id"), nullable=False),
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
    CheckConstraint("LENGTH(name) >= 3", name="ck_golf_courses_name_min_length"),
    CheckConstraint(
        "(approval_status != 'REJECTED') OR (rejection_reason IS NOT NULL)",
        name="ck_golf_courses_rejection_reason_required",
    ),
    comment="Campos de golf con workflow de aprobación Admin",
)

golf_course_tees_table = Table(
    "golf_course_tees",
    mapper_registry.metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column(
        "golf_course_id",
        UUID(as_uuid=True),
        ForeignKey("golf_courses.id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column(
        "tee_category",
        SQLEnum(TeeCategory, name="tee_category_enum", create_type=False),
        nullable=False,
        comment="Categoría normalizada WHS (CHAMPIONSHIP_MALE, etc.)",
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
    UniqueConstraint("golf_course_id", "tee_category", name="uq_golf_course_tees_category"),
    comment="Tees (salidas) de campos de golf con ratings WHS",
)

golf_course_holes_table = Table(
    "golf_course_holes",
    mapper_registry.metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column(
        "golf_course_id",
        UUID(as_uuid=True),
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
# TypeDecorators for Value Objects
# ============================================================================


class GolfCourseIdType(sqlalchemy.types.TypeDecorator[GolfCourseId]):
    """TypeDecorator para GolfCourseId Value Object."""

    impl = UUID(as_uuid=True)
    cache_ok = True

    def process_bind_param(self, value: GolfCourseId | None, dialect: Any) -> uuid.UUID | None:
        """Convierte GolfCourseId → UUID para persistencia."""
        if value is None:
            return None
        return uuid.UUID(value.value)

    def process_result_value(self, value: uuid.UUID | None, dialect: Any) -> GolfCourseId | None:
        """Convierte UUID → GolfCourseId al hidratar."""
        if value is None:
            return None
        return GolfCourseId(str(value))


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
    """TypeDecorator para UserId Value Object."""

    impl = UUID(as_uuid=True)
    cache_ok = True

    def process_bind_param(self, value: UserId | None, dialect: Any) -> uuid.UUID | None:
        """Convierte UserId → UUID para persistencia."""
        if value is None:
            return None
        return value.value

    def process_result_value(self, value: uuid.UUID | None, dialect: Any) -> UserId | None:
        """Convierte UUID → UserId al hidratar."""
        if value is None:
            return None
        return UserId(value)


# ============================================================================
# Imperative Mapping
# ============================================================================

mapper_registry.map_imperatively(
    Tee,
    golf_course_tees_table,
    properties={
        # Map database column tee_category to entity attribute category
        "category": golf_course_tees_table.c.tee_category,
    },
)

mapper_registry.map_imperatively(
    Hole,
    golf_course_holes_table,
    properties={
        # Map database column hole_number to entity attribute number
        "number": golf_course_holes_table.c.hole_number,
    },
)

mapper_registry.map_imperatively(
    GolfCourse,
    golf_courses_table,
    properties={
        # Value Objects mapping with TypeDecorators
        "_id": Column("id", GolfCourseIdType),
        "_country_code": Column("country_code", CountryCodeType),
        "_creator_id": Column("creator_id", UserIdType),
        # Scalar attributes mapping
        "_name": golf_courses_table.c.name,
        "_course_type": golf_courses_table.c.course_type,
        "_approval_status": golf_courses_table.c.approval_status,
        "_rejection_reason": golf_courses_table.c.rejection_reason,
        "_created_at": golf_courses_table.c.created_at,
        "_updated_at": golf_courses_table.c.updated_at,
        # One-to-many relationships with tees and holes
        "_tees": relationship(
            Tee,
            cascade="all, delete-orphan",
            lazy="joined",  # Eager loading
            order_by=golf_course_tees_table.c.id,
        ),
        "_holes": relationship(
            Hole,
            cascade="all, delete-orphan",
            lazy="joined",  # Eager loading
            order_by=golf_course_holes_table.c.hole_number,  # DB column name
        ),
        # Domain events (transient, not persisted)
        "_domain_events": [],
    },
)
