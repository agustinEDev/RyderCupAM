"""
Competition and Enrollment Mappers - SQLAlchemy Imperative Mapping.

Mapea las entidades Competition y Enrollment del dominio a las tablas de PostgreSQL.
Sigue el patrón Imperative Mapping establecido en el módulo User.
"""

import uuid
from datetime import date

from sqlalchemy import (
    Column,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Table,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import composite, relationship
from sqlalchemy.types import CHAR, TypeDecorator

# Domain Entities
from src.modules.competition.domain.entities.competition import Competition
from src.modules.competition.domain.entities.competition_golf_course import (
    CompetitionGolfCourse,
)
from src.modules.competition.domain.entities.enrollment import Enrollment

# Value Objects - Competition
from src.modules.competition.domain.value_objects.competition_golf_course_id import (
    CompetitionGolfCourseId,
)
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.competition_name import (
    CompetitionName,
)
from src.modules.competition.domain.value_objects.competition_status import (
    CompetitionStatus,
)
from src.modules.competition.domain.value_objects.date_range import DateRange
from src.modules.competition.domain.value_objects.enrollment_id import EnrollmentId
from src.modules.competition.domain.value_objects.enrollment_status import (
    EnrollmentStatus,
)
from src.modules.competition.domain.value_objects.handicap_settings import (
    HandicapSettings,
    HandicapType,
)
from src.modules.competition.domain.value_objects.location import Location
from src.modules.competition.domain.value_objects.team_assignment import TeamAssignment

# Golf Course Entity and Value Object (FK)
from src.modules.golf_course.domain.entities.golf_course import GolfCourse
from src.modules.golf_course.domain.value_objects.golf_course_id import GolfCourseId

# User Value Object (FK)
from src.modules.user.domain.value_objects.user_id import UserId

# Shared Value Objects
from src.shared.domain.value_objects.country_code import CountryCode

# Importar registry y metadata centralizados
from src.shared.infrastructure.persistence.sqlalchemy.base import (
    mapper_registry,
    metadata,
)

COUNTRIES_CODE_FK = "countries.code"

# =============================================================================
# TYPE DECORATORS - Para Value Objects complejos (IDs)
# =============================================================================


class CompetitionIdDecorator(TypeDecorator):
    """
    TypeDecorator para convertir CompetitionId (UUID VO) a/desde VARCHAR(36).
    """

    impl = CHAR(36)
    cache_ok = True

    def process_bind_param(self, value: CompetitionId | str | None, dialect) -> str | None:
        """Convierte CompetitionId o str a string para BD."""
        if isinstance(value, CompetitionId):
            return str(value.value)
        if isinstance(value, str):
            return value
        return None

    def process_result_value(self, value: str | None, dialect) -> CompetitionId | None:
        """Convierte string de BD a CompetitionId."""
        if value is None:
            return None
        return CompetitionId(uuid.UUID(value))


class EnrollmentIdDecorator(TypeDecorator):
    """
    TypeDecorator para convertir EnrollmentId (UUID VO) a/desde VARCHAR(36).
    """

    impl = CHAR(36)
    cache_ok = True

    def process_bind_param(self, value: EnrollmentId | str | None, dialect) -> str | None:
        """Convierte EnrollmentId o str a string para BD."""
        if isinstance(value, EnrollmentId):
            return str(value.value)
        if isinstance(value, str):
            return value
        return None

    def process_result_value(self, value: str | None, dialect) -> EnrollmentId | None:
        """Convierte string de BD a EnrollmentId."""
        if value is None:
            return None
        return EnrollmentId(uuid.UUID(value))


class UserIdDecorator(TypeDecorator):
    """
    TypeDecorator para convertir UserId (UUID VO) a/desde VARCHAR(36).
    Reutilizado desde el módulo User para FKs.
    """

    impl = CHAR(36)
    cache_ok = True

    def process_bind_param(self, value: UserId | str | None, dialect) -> str | None:
        """Convierte UserId o str a string para BD."""
        if isinstance(value, UserId):
            return str(value.value)
        if isinstance(value, str):
            return value
        return None

    def process_result_value(self, value: str | None, dialect) -> UserId | None:
        """Convierte string de BD a UserId."""
        if value is None:
            return None
        return UserId(uuid.UUID(value))


class CountryCodeDecorator(TypeDecorator):
    """
    TypeDecorator para convertir CountryCode (str VO) a/desde VARCHAR(2).
    """

    impl = CHAR(2)
    cache_ok = True

    def process_bind_param(self, value: CountryCode | str | None, dialect) -> str | None:
        """Convierte CountryCode o str a string para BD."""
        if isinstance(value, CountryCode):
            return str(value.value)
        if isinstance(value, str):
            return value
        return None

    def process_result_value(self, value: str | None, dialect) -> CountryCode | None:
        """Convierte string de BD a CountryCode."""
        if value is None:
            return None
        return CountryCode(value)


class CompetitionGolfCourseIdDecorator(TypeDecorator):
    """
    TypeDecorator para convertir CompetitionGolfCourseId (UUID VO) a/desde VARCHAR(36).
    """

    impl = CHAR(36)
    cache_ok = True

    def process_bind_param(
        self, value: CompetitionGolfCourseId | str | None, dialect
    ) -> str | None:
        """Convierte CompetitionGolfCourseId o str a string para BD."""
        if isinstance(value, CompetitionGolfCourseId):
            return str(value.value)
        if isinstance(value, str):
            return value
        return None

    def process_result_value(
        self, value: str | None, dialect
    ) -> CompetitionGolfCourseId | None:
        """Convierte string de BD a CompetitionGolfCourseId."""
        if value is None:
            return None
        return CompetitionGolfCourseId(uuid.UUID(value))


class GolfCourseIdDecorator(TypeDecorator):
    """
    TypeDecorator para convertir GolfCourseId (UUID VO) a/desde UUID nativo.

    IMPORTANTE: Debe coincidir con el tipo usado en golf_courses.id (UUID as_uuid=True)
    """

    impl = UUID(as_uuid=True)
    cache_ok = True

    def process_bind_param(self, value: GolfCourseId | None, dialect) -> uuid.UUID | None:
        """Convierte GolfCourseId a UUID para BD."""
        if value is None:
            return None
        if isinstance(value, GolfCourseId):
            return value.value
        return uuid.UUID(str(value))

    def process_result_value(self, value: uuid.UUID | None, dialect) -> GolfCourseId | None:
        """Convierte UUID de BD a GolfCourseId."""
        if value is None:
            return None
        return GolfCourseId(value)


# =============================================================================
# COMPOSITE VALUE OBJECTS - Helpers para reconstrucción
# =============================================================================


class CompetitionNameComposite:
    """
    Composite helper para CompetitionName Value Object.

    SQLAlchemy composite() requiere un callable que reciba los valores de BD
    y retorne el Value Object.
    """

    def __init__(self, name: str):
        if name:
            self.value = CompetitionName(name)
        else:
            self.value = None

    def __composite_values__(self):
        """Devuelve los valores para persistir en BD."""
        return (str(self.value) if self.value else None,)

    def __eq__(self, other):
        return isinstance(other, CompetitionNameComposite) and self.value == other.value

    def __ne__(self, other):
        return not self.__eq__(other)

    def __hash__(self):
        return hash(str(self.value) if self.value else None)


class DateRangeComposite:
    """
    Composite helper para DateRange Value Object.

    Maneja la reconstrucción desde 2 columnas: start_date, end_date.
    """

    def __init__(self, start_date: date, end_date: date):
        if start_date and end_date:
            self.value = DateRange(start_date, end_date)
        else:
            self.value = None

    def __composite_values__(self):
        """Devuelve los valores para persistir en BD."""
        if self.value:
            return (self.value.start_date, self.value.end_date)
        return (None, None)

    def __eq__(self, other):
        return isinstance(other, DateRangeComposite) and self.value == other.value

    def __ne__(self, other):
        return not self.__eq__(other)

    def __hash__(self):
        if self.value:
            return hash((self.value.start_date, self.value.end_date))
        return hash(None)


class LocationComposite:
    """
    Composite helper para Location Value Object.

    Maneja la reconstrucción desde 3 columnas:
    - country_code (main_country)
    - secondary_country_code (adjacent_country_1)
    - tertiary_country_code (adjacent_country_2)
    """

    def __init__(
        self,
        country_code: CountryCode | None,
        secondary_country_code: CountryCode | None = None,
        tertiary_country_code: CountryCode | None = None,
    ):
        if country_code:
            self.value = Location(
                main_country=country_code,
                adjacent_country_1=secondary_country_code,
                adjacent_country_2=tertiary_country_code,
            )
        else:
            self.value = None

    def __composite_values__(self):
        """Devuelve los valores para persistir en BD."""
        if self.value:
            return (
                self.value.main_country,
                self.value.adjacent_country_1,
                self.value.adjacent_country_2,
            )
        return (None, None, None)

    def __eq__(self, other):
        return isinstance(other, LocationComposite) and self.value == other.value

    def __ne__(self, other):
        return not self.__eq__(other)

    def __hash__(self):
        if self.value:
            return hash(
                (
                    self.value.main_country,
                    self.value.adjacent_country_1,
                    self.value.adjacent_country_2,
                )
            )
        return hash(None)


class HandicapSettingsComposite:
    """
    Composite helper para HandicapSettings Value Object.

    Maneja la reconstrucción desde 2 columnas:
    - handicap_type (str → HandicapType enum)
    - handicap_value (int)
    """

    def __init__(self, handicap_type: str, handicap_value: int | None):
        if handicap_type:
            # Convertir string de BD a enum
            h_type = HandicapType(handicap_type)
            self.value = HandicapSettings(h_type, handicap_value)
        else:
            self.value = None

    def __composite_values__(self):
        """Devuelve los valores para persistir en BD."""
        if self.value:
            return (self.value.type.value, self.value.percentage)
        return (None, None)

    def __eq__(self, other):
        return isinstance(other, HandicapSettingsComposite) and self.value == other.value

    def __ne__(self, other):
        return not self.__eq__(other)

    def __hash__(self):
        if self.value:
            return hash((self.value.type.value, self.value.percentage))
        return hash(None)


class CompetitionStatusComposite:
    """
    Composite helper para CompetitionStatus Value Object.

    Convierte string de BD a enum CompetitionStatus.
    """

    def __init__(self, status: str):
        if status:
            self.value = CompetitionStatus(status)
        else:
            self.value = None

    def __composite_values__(self):
        """Devuelve los valores para persistir en BD."""
        return (self.value.value if self.value else None,)

    def __eq__(self, other):
        return isinstance(other, CompetitionStatusComposite) and self.value == other.value

    def __ne__(self, other):
        return not self.__eq__(other)

    def __hash__(self):
        return hash(self.value.value if self.value else None)


class EnrollmentStatusComposite:
    """
    Composite helper para EnrollmentStatus Value Object.

    Convierte string de BD a enum EnrollmentStatus.
    """

    def __init__(self, status: str):
        if status:
            self.value = EnrollmentStatus(status)
        else:
            self.value = None

    def __composite_values__(self):
        """Devuelve los valores para persistir en BD."""
        return (self.value.value if self.value else None,)

    def __eq__(self, other):
        return isinstance(other, EnrollmentStatusComposite) and self.value == other.value

    def __ne__(self, other):
        return not self.__eq__(other)

    def __hash__(self):
        return hash(self.value.value if self.value else None)


# =============================================================================
# REGISTRY Y METADATA
# =============================================================================

# (Importados de base.py - ver imports arriba)


# =============================================================================
# TABLA COMPETITIONS
# =============================================================================

competitions_table = Table(
    "competitions",
    metadata,
    Column("id", CompetitionIdDecorator, primary_key=True),
    Column(
        "creator_id",
        UserIdDecorator,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column("name", String(200), nullable=False),
    Column("start_date", Date, nullable=False),
    Column("end_date", Date, nullable=False),
    Column(
        "country_code",
        CountryCodeDecorator,
        ForeignKey(COUNTRIES_CODE_FK, ondelete="RESTRICT"),
        nullable=False,
    ),
    Column(
        "secondary_country_code",
        CountryCodeDecorator,
        ForeignKey(COUNTRIES_CODE_FK, ondelete="RESTRICT"),
        nullable=True,
    ),
    Column(
        "tertiary_country_code",
        CountryCodeDecorator,
        ForeignKey(COUNTRIES_CODE_FK, ondelete="RESTRICT"),
        nullable=True,
    ),
    Column("team_1_name", String(100), nullable=False),
    Column("team_2_name", String(100), nullable=False),
    Column("handicap_type", String(20), nullable=False),
    Column("handicap_value", Integer, nullable=True),
    Column("max_players", Integer, nullable=False, default=24),
    Column("team_assignment", String(20), nullable=False, default="MANUAL"),
    Column("status", String(20), nullable=False, default="DRAFT"),
    Column("created_at", DateTime, nullable=False),
    Column("updated_at", DateTime, nullable=False),
)


# =============================================================================
# TABLA ENROLLMENTS
# =============================================================================

enrollments_table = Table(
    "enrollments",
    metadata,
    Column("id", EnrollmentIdDecorator, primary_key=True),
    Column(
        "competition_id",
        CompetitionIdDecorator,
        ForeignKey("competitions.id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column(
        "user_id",
        UserIdDecorator,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column("status", String(20), nullable=False),
    Column("team_id", String(10), nullable=True),
    Column("custom_handicap", Numeric(precision=4, scale=1), nullable=True),
    Column("created_at", DateTime, nullable=False),
    Column("updated_at", DateTime, nullable=False),
)


# =============================================================================
# TABLA COMPETITION_GOLF_COURSES (Association Table)
# =============================================================================

competition_golf_courses_table = Table(
    "competition_golf_courses",
    metadata,
    Column("id", CompetitionGolfCourseIdDecorator, primary_key=True),
    Column(
        "competition_id",
        CompetitionIdDecorator,
        ForeignKey("competitions.id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column(
        "golf_course_id",
        GolfCourseIdDecorator,
        ForeignKey("golf_courses.id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column("display_order", Integer, nullable=False),
    Column("created_at", DateTime, nullable=False),
)


# =============================================================================
# START MAPPERS - Función de inicialización
# =============================================================================


def start_competition_mappers():
    """
    Inicia el mapeo entre entidades de dominio y tablas de BD.

    Es idempotente - puede llamarse múltiples veces sin problemas.

    Mapea:
    - Competition entity → competitions table
    - Enrollment entity → enrollments table

    Note:
        Los mappers de Country están en shared/infrastructure/persistence/sqlalchemy/country_mappers.py
    """
    # Mapear Competition
    if Competition not in mapper_registry.mappers:
        mapper_registry.map_imperatively(
            Competition,
            competitions_table,
            properties={
                # Mapear Value Objects complejos usando composite()
                # IMPORTANTE: Usamos atributos "privados" (_xxx) para evitar
                # que SQLAlchemy intente mapear automáticamente los públicos
                # 1. CompetitionName
                "_name_value": competitions_table.c.name,
                "name": composite(lambda n: CompetitionName(n) if n else None, "_name_value"),
                # 2. DateRange
                "_start_date": competitions_table.c.start_date,
                "_end_date": competitions_table.c.end_date,
                "dates": composite(
                    lambda s, e: DateRange(s, e) if s and e else None,
                    "_start_date",
                    "_end_date",
                ),
                # 3. Location (3 países)
                "_country_code": competitions_table.c.country_code,
                "_secondary_country_code": competitions_table.c.secondary_country_code,
                "_tertiary_country_code": competitions_table.c.tertiary_country_code,
                "location": composite(
                    lambda c1, c2, c3: (
                        Location(
                            main_country=c1,
                            adjacent_country_1=c2,
                            adjacent_country_2=c3,
                        )
                        if c1
                        else None
                    ),
                    "_country_code",
                    "_secondary_country_code",
                    "_tertiary_country_code",
                ),
                # 4. HandicapSettings
                "_handicap_type": competitions_table.c.handicap_type,
                "_handicap_value": competitions_table.c.handicap_value,
                "handicap_settings": composite(
                    lambda t, v: HandicapSettings(HandicapType(t), v) if t else None,
                    "_handicap_type",
                    "_handicap_value",
                ),
                # 5. CompetitionStatus (enum)
                "_status_value": competitions_table.c.status,
                "status": composite(
                    lambda s: CompetitionStatus(s) if s else CompetitionStatus.DRAFT,
                    "_status_value",
                ),
                # 6. TeamAssignment (enum)
                "_team_assignment_value": competitions_table.c.team_assignment,
                "team_assignment": composite(
                    lambda t: TeamAssignment(t) if t else TeamAssignment.MANUAL,
                    "_team_assignment_value",
                ),
                # 7. max_players - Mapeo directo (mismo nombre)
                "max_players": competitions_table.c.max_players,
                # 8. Relationship con CompetitionGolfCourse (One-to-Many)
                "_golf_courses": relationship(
                    CompetitionGolfCourse,
                    cascade="all, delete-orphan",
                    order_by=competition_golf_courses_table.c.display_order,
                    foreign_keys=[competition_golf_courses_table.c.competition_id],
                ),
            },
        )

    # Mapear Enrollment
    if Enrollment not in mapper_registry.mappers:
        mapper_registry.map_imperatively(
            Enrollment,
            enrollments_table,
            properties={
                # 1. EnrollmentStatus (enum) - mismo patrón que Competition
                "_status_value": enrollments_table.c.status,
                "status": composite(EnrollmentStatus, "_status_value"),
                # 2. custom_handicap - Mapeo directo Decimal (ya está en el dominio)
                # SQLAlchemy lo mapea automáticamente, pero lo hacemos explícito
                "custom_handicap": enrollments_table.c.custom_handicap,
            },
        )

    # Mapear CompetitionGolfCourse (Association Entity)
    if CompetitionGolfCourse not in mapper_registry.mappers:
        mapper_registry.map_imperatively(
            CompetitionGolfCourse,
            competition_golf_courses_table,
            properties={
                # Mapeo explícito para que SQLAlchemy reconozca los atributos privados
                "_id": competition_golf_courses_table.c.id,
                "_competition_id": competition_golf_courses_table.c.competition_id,
                "_golf_course_id": competition_golf_courses_table.c.golf_course_id,
                "_display_order": competition_golf_courses_table.c.display_order,
                "_created_at": competition_golf_courses_table.c.created_at,
                # Relationship to load the full GolfCourse entity
                "golf_course": relationship(
                    GolfCourse,
                    foreign_keys=[competition_golf_courses_table.c.golf_course_id],
                    lazy="select",  # Will be overridden by explicit joinedload() in queries
                ),
            },
        )


def start_mappers():
    """
    Inicia los mappers de Competition, Enrollment y CompetitionGolfCourse.

    Esta función debe ser llamada al inicio de la aplicación (en main.py)
    para registrar los mappers de SQLAlchemy antes de realizar cualquier
    operación con la base de datos.

    Es idempotente: puede llamarse múltiples veces sin efectos adversos.
    """
    start_competition_mappers()
