"""
Competition Module Mappers - SQLAlchemy Imperative Mapping.

Mapea las entidades del dominio de Competition a las tablas de PostgreSQL.
Sigue el patron Imperative Mapping establecido en el modulo User.
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
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import composite, relationship
from sqlalchemy.types import CHAR, TypeDecorator

# Domain Entities
from src.modules.competition.domain.entities.competition import Competition
from src.modules.competition.domain.entities.competition_golf_course import (
    CompetitionGolfCourse,
)
from src.modules.competition.domain.entities.enrollment import Enrollment
from src.modules.competition.domain.entities.match import Match
from src.modules.competition.domain.entities.round import Round
from src.modules.competition.domain.entities.team_assignment import (
    TeamAssignment as TeamAssignmentEntity,
)

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
from src.modules.competition.domain.value_objects.handicap_mode import HandicapMode
from src.modules.competition.domain.value_objects.location import Location
from src.modules.competition.domain.value_objects.match_format import MatchFormat
from src.modules.competition.domain.value_objects.match_id import MatchId
from src.modules.competition.domain.value_objects.match_player import MatchPlayer
from src.modules.competition.domain.value_objects.match_status import MatchStatus
from src.modules.competition.domain.value_objects.play_mode import PlayMode
from src.modules.competition.domain.value_objects.round_id import RoundId
from src.modules.competition.domain.value_objects.round_status import RoundStatus
from src.modules.competition.domain.value_objects.session_type import SessionType
from src.modules.competition.domain.value_objects.team_assignment import (
    TeamAssignment as TeamAssignmentVO,
)
from src.modules.competition.domain.value_objects.team_assignment_id import (
    TeamAssignmentId,
)
from src.modules.competition.domain.value_objects.team_assignment_mode import (
    TeamAssignmentMode,
)

# Golf Course Entity and Value Object (FK)
from src.modules.golf_course.domain.entities.golf_course import GolfCourse
from src.modules.golf_course.domain.value_objects.golf_course_id import GolfCourseId
from src.modules.golf_course.domain.value_objects.tee_category import TeeCategory

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
    """TypeDecorator para convertir CompetitionId (UUID VO) a/desde VARCHAR(36)."""

    impl = CHAR(36)
    cache_ok = True

    def process_bind_param(self, value: CompetitionId | str | None, dialect) -> str | None:
        if isinstance(value, CompetitionId):
            return str(value.value)
        if isinstance(value, str):
            return value
        return None

    def process_result_value(self, value: str | None, dialect) -> CompetitionId | None:
        if value is None:
            return None
        return CompetitionId(uuid.UUID(value))


class EnrollmentIdDecorator(TypeDecorator):
    """TypeDecorator para convertir EnrollmentId (UUID VO) a/desde VARCHAR(36)."""

    impl = CHAR(36)
    cache_ok = True

    def process_bind_param(self, value: EnrollmentId | str | None, dialect) -> str | None:
        if isinstance(value, EnrollmentId):
            return str(value.value)
        if isinstance(value, str):
            return value
        return None

    def process_result_value(self, value: str | None, dialect) -> EnrollmentId | None:
        if value is None:
            return None
        return EnrollmentId(uuid.UUID(value))


class UserIdDecorator(TypeDecorator):
    """TypeDecorator para convertir UserId (UUID VO) a/desde VARCHAR(36)."""

    impl = CHAR(36)
    cache_ok = True

    def process_bind_param(self, value: UserId | str | None, dialect) -> str | None:
        if isinstance(value, UserId):
            return str(value.value)
        if isinstance(value, str):
            return value
        return None

    def process_result_value(self, value: str | None, dialect) -> UserId | None:
        if value is None:
            return None
        return UserId(uuid.UUID(value))


class CountryCodeDecorator(TypeDecorator):
    """TypeDecorator para convertir CountryCode (str VO) a/desde VARCHAR(2)."""

    impl = CHAR(2)
    cache_ok = True

    def process_bind_param(self, value: CountryCode | str | None, dialect) -> str | None:
        if isinstance(value, CountryCode):
            return str(value.value)
        if isinstance(value, str):
            return value
        return None

    def process_result_value(self, value: str | None, dialect) -> CountryCode | None:
        if value is None:
            return None
        return CountryCode(value)


class CompetitionGolfCourseIdDecorator(TypeDecorator):
    """TypeDecorator para convertir CompetitionGolfCourseId (UUID VO) a/desde VARCHAR(36)."""

    impl = CHAR(36)
    cache_ok = True

    def process_bind_param(
        self, value: CompetitionGolfCourseId | str | None, dialect
    ) -> str | None:
        if isinstance(value, CompetitionGolfCourseId):
            return str(value.value)
        if isinstance(value, str):
            return value
        return None

    def process_result_value(self, value: str | None, dialect) -> CompetitionGolfCourseId | None:
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
        if value is None:
            return None
        if isinstance(value, GolfCourseId):
            return value.value
        return uuid.UUID(str(value))

    def process_result_value(self, value: uuid.UUID | None, dialect) -> GolfCourseId | None:
        if value is None:
            return None
        return GolfCourseId(value)


class RoundIdDecorator(TypeDecorator):
    """TypeDecorator para convertir RoundId (UUID VO) a/desde VARCHAR(36)."""

    impl = CHAR(36)
    cache_ok = True

    def process_bind_param(self, value: RoundId | str | None, dialect) -> str | None:
        if isinstance(value, RoundId):
            return str(value.value)
        if isinstance(value, str):
            return value
        return None

    def process_result_value(self, value: str | None, dialect) -> RoundId | None:
        if value is None:
            return None
        return RoundId(uuid.UUID(value))


class MatchIdDecorator(TypeDecorator):
    """TypeDecorator para convertir MatchId (UUID VO) a/desde VARCHAR(36)."""

    impl = CHAR(36)
    cache_ok = True

    def process_bind_param(self, value: MatchId | str | None, dialect) -> str | None:
        if isinstance(value, MatchId):
            return str(value.value)
        if isinstance(value, str):
            return value
        return None

    def process_result_value(self, value: str | None, dialect) -> MatchId | None:
        if value is None:
            return None
        return MatchId(uuid.UUID(value))


class TeamAssignmentIdDecorator(TypeDecorator):
    """TypeDecorator para convertir TeamAssignmentId (UUID VO) a/desde VARCHAR(36)."""

    impl = CHAR(36)
    cache_ok = True

    def process_bind_param(self, value: TeamAssignmentId | str | None, dialect) -> str | None:
        if isinstance(value, TeamAssignmentId):
            return str(value.value)
        if isinstance(value, str):
            return value
        return None

    def process_result_value(self, value: str | None, dialect) -> TeamAssignmentId | None:
        if value is None:
            return None
        return TeamAssignmentId(uuid.UUID(value))


# =============================================================================
# TYPE DECORATORS - Enum string conversion
# =============================================================================


def _create_enum_decorator(enum_class: type) -> type:
    """Factory para crear TypeDecorators que convierten str <-> Enum."""

    class Decorator(TypeDecorator):
        impl = String(20)
        cache_ok = True

        def process_bind_param(self, value, dialect):
            if value is None:
                return None
            if hasattr(value, "value"):
                return value.value
            return value

        def process_result_value(self, value, dialect):
            if value is None:
                return None
            return enum_class(value)

    Decorator.__name__ = f"{enum_class.__name__}Decorator"
    Decorator.__qualname__ = f"{enum_class.__name__}Decorator"
    return Decorator


SessionTypeDecorator = _create_enum_decorator(SessionType)
MatchFormatDecorator = _create_enum_decorator(MatchFormat)
RoundStatusDecorator = _create_enum_decorator(RoundStatus)
HandicapModeDecorator = _create_enum_decorator(HandicapMode)
MatchStatusDecorator = _create_enum_decorator(MatchStatus)
TeamAssignmentModeDecorator = _create_enum_decorator(TeamAssignmentMode)
TeeCategoryDecorator = _create_enum_decorator(TeeCategory)
PlayModeDecorator = _create_enum_decorator(PlayMode)


# =============================================================================
# TYPE DECORATORS - JSONB para Value Objects complejos
# =============================================================================


class MatchPlayersJsonType(TypeDecorator):
    """
    TypeDecorator para serializar tuple[MatchPlayer, ...] a/desde JSONB.

    Cada MatchPlayer se serializa como:
    {
        "user_id": "uuid-string",
        "playing_handicap": 12,
        "tee_category": "AMATEUR_MALE",
        "strokes_received": [1, 3, 5, 7]
    }
    """

    impl = JSONB
    cache_ok = True

    def process_bind_param(self, value: tuple | list | None, dialect) -> list | None:
        if value is None:
            return None
        return [
            {
                "user_id": str(p.user_id.value),
                "playing_handicap": p.playing_handicap,
                "tee_category": p.tee_category.value,
                "strokes_received": list(p.strokes_received),
            }
            for p in value
        ]

    def process_result_value(self, value: list | None, dialect) -> tuple | None:
        if value is None:
            return None
        players = []
        for p in value:
            player = MatchPlayer(
                user_id=UserId(uuid.UUID(p["user_id"])),
                playing_handicap=p["playing_handicap"],
                tee_category=TeeCategory(p["tee_category"]),
                strokes_received=tuple(p["strokes_received"]),
            )
            players.append(player)
        return tuple(players)


class UserIdsJsonType(TypeDecorator):
    """
    TypeDecorator para serializar tuple[UserId, ...] a/desde JSONB.

    Se almacena como array de strings UUID: ["uuid-1", "uuid-2", ...]
    """

    impl = JSONB
    cache_ok = True

    def process_bind_param(self, value: tuple | list | None, dialect) -> list | None:
        if value is None:
            return None
        return [str(uid.value) for uid in value]

    def process_result_value(self, value: list | None, dialect) -> tuple | None:
        if value is None:
            return None
        return tuple(UserId(uuid.UUID(uid_str)) for uid_str in value)


class MatchResultJsonType(TypeDecorator):
    """TypeDecorator pass-through para dict | None almacenado como JSONB."""

    impl = JSONB
    cache_ok = True

    def process_bind_param(self, value: dict | None, dialect) -> dict | None:
        return value

    def process_result_value(self, value: dict | None, dialect) -> dict | None:
        return value


# =============================================================================
# COMPOSITE VALUE OBJECTS - Helpers para reconstruccion
# =============================================================================


class CompetitionNameComposite:
    """Composite helper para CompetitionName Value Object."""

    def __init__(self, name: str):
        if name:
            self.value = CompetitionName(name)
        else:
            self.value = None

    def __composite_values__(self):
        return (str(self.value) if self.value else None,)

    def __eq__(self, other):
        return isinstance(other, CompetitionNameComposite) and self.value == other.value

    def __ne__(self, other):
        return not self.__eq__(other)

    def __hash__(self):
        return hash(str(self.value) if self.value else None)


class DateRangeComposite:
    """Composite helper para DateRange Value Object."""

    def __init__(self, start_date: date, end_date: date):
        if start_date and end_date:
            self.value = DateRange(start_date, end_date)
        else:
            self.value = None

    def __composite_values__(self):
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
    """Composite helper para Location Value Object (3 columnas)."""

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


class CompetitionStatusComposite:
    """Composite helper para CompetitionStatus enum."""

    def __init__(self, status: str):
        if status:
            self.value = CompetitionStatus(status)
        else:
            self.value = None

    def __composite_values__(self):
        return (self.value.value if self.value else None,)

    def __eq__(self, other):
        return isinstance(other, CompetitionStatusComposite) and self.value == other.value

    def __ne__(self, other):
        return not self.__eq__(other)

    def __hash__(self):
        return hash(self.value.value if self.value else None)


class EnrollmentStatusComposite:
    """Composite helper para EnrollmentStatus enum."""

    def __init__(self, status: str):
        if status:
            self.value = EnrollmentStatus(status)
        else:
            self.value = None

    def __composite_values__(self):
        return (self.value.value if self.value else None,)

    def __eq__(self, other):
        return isinstance(other, EnrollmentStatusComposite) and self.value == other.value

    def __ne__(self, other):
        return not self.__eq__(other)

    def __hash__(self):
        return hash(self.value.value if self.value else None)


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
    Column("play_mode", PlayModeDecorator, nullable=False),
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
    Column("tee_category", TeeCategoryDecorator, nullable=True),
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
# TABLA ROUNDS
# =============================================================================

rounds_table = Table(
    "rounds",
    metadata,
    Column("id", RoundIdDecorator, primary_key=True),
    Column(
        "competition_id",
        CompetitionIdDecorator,
        ForeignKey("competitions.id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column(
        "golf_course_id",
        GolfCourseIdDecorator,
        ForeignKey("golf_courses.id", ondelete="RESTRICT"),
        nullable=False,
    ),
    Column("round_date", Date, nullable=False),
    Column("session_type", SessionTypeDecorator, nullable=False),
    Column("match_format", MatchFormatDecorator, nullable=False),
    Column("status", RoundStatusDecorator, nullable=False),
    Column("handicap_mode", HandicapModeDecorator, nullable=True),
    Column("allowance_percentage", Integer, nullable=True),
    Column("created_at", DateTime, nullable=False),
    Column("updated_at", DateTime, nullable=False),
)


# =============================================================================
# TABLA MATCHES
# =============================================================================

matches_table = Table(
    "matches",
    metadata,
    Column("id", MatchIdDecorator, primary_key=True),
    Column(
        "round_id",
        RoundIdDecorator,
        ForeignKey("rounds.id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column("match_number", Integer, nullable=False),
    Column("team_a_players", MatchPlayersJsonType, nullable=False),
    Column("team_b_players", MatchPlayersJsonType, nullable=False),
    Column("status", MatchStatusDecorator, nullable=False),
    Column("handicap_strokes_given", Integer, nullable=False, default=0),
    Column("strokes_given_to_team", String(1), nullable=False, default=""),
    Column("result", MatchResultJsonType, nullable=True),
    Column("created_at", DateTime, nullable=False),
    Column("updated_at", DateTime, nullable=False),
)


# =============================================================================
# TABLA TEAM_ASSIGNMENTS
# =============================================================================

team_assignments_table = Table(
    "team_assignments",
    metadata,
    Column("id", TeamAssignmentIdDecorator, primary_key=True),
    Column(
        "competition_id",
        CompetitionIdDecorator,
        ForeignKey("competitions.id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column("mode", TeamAssignmentModeDecorator, nullable=False),
    Column("team_a_player_ids", UserIdsJsonType, nullable=False),
    Column("team_b_player_ids", UserIdsJsonType, nullable=False),
    Column("created_at", DateTime, nullable=False),
)


# =============================================================================
# START MAPPERS - Funcion de inicializacion
# =============================================================================


def start_competition_mappers():
    """
    Inicia el mapeo entre entidades de dominio y tablas de BD.

    Es idempotente - puede llamarse multiples veces sin problemas.

    Mapea:
    - Competition entity -> competitions table
    - Enrollment entity -> enrollments table
    - CompetitionGolfCourse entity -> competition_golf_courses table
    - Round entity -> rounds table
    - Match entity -> matches table
    - TeamAssignment entity -> team_assignments table
    """
    # Mapear Competition
    if Competition not in mapper_registry.mappers:
        mapper_registry.map_imperatively(
            Competition,
            competitions_table,
            properties={
                "_name_value": competitions_table.c.name,
                "name": composite(lambda n: CompetitionName(n) if n else None, "_name_value"),
                "_start_date": competitions_table.c.start_date,
                "_end_date": competitions_table.c.end_date,
                "dates": composite(
                    lambda s, e: DateRange(s, e) if s and e else None,
                    "_start_date",
                    "_end_date",
                ),
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
                "play_mode": competitions_table.c.play_mode,
                "_status_value": competitions_table.c.status,
                "status": composite(
                    lambda s: CompetitionStatus(s) if s else CompetitionStatus.DRAFT,
                    "_status_value",
                ),
                "_team_assignment_value": competitions_table.c.team_assignment,
                "team_assignment": composite(
                    lambda t: TeamAssignmentVO(t) if t else TeamAssignmentVO.MANUAL,
                    "_team_assignment_value",
                ),
                "max_players": competitions_table.c.max_players,
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
                "_status_value": enrollments_table.c.status,
                "status": composite(EnrollmentStatus, "_status_value"),
                "custom_handicap": enrollments_table.c.custom_handicap,
            },
        )

    # Mapear CompetitionGolfCourse (Association Entity)
    if CompetitionGolfCourse not in mapper_registry.mappers:
        mapper_registry.map_imperatively(
            CompetitionGolfCourse,
            competition_golf_courses_table,
            properties={
                "_id": competition_golf_courses_table.c.id,
                "_competition_id": competition_golf_courses_table.c.competition_id,
                "_golf_course_id": competition_golf_courses_table.c.golf_course_id,
                "_display_order": competition_golf_courses_table.c.display_order,
                "_created_at": competition_golf_courses_table.c.created_at,
                "golf_course": relationship(
                    GolfCourse,
                    foreign_keys=[competition_golf_courses_table.c.golf_course_id],
                    lazy="select",
                ),
            },
        )

    # Mapear Round
    if Round not in mapper_registry.mappers:
        mapper_registry.map_imperatively(
            Round,
            rounds_table,
            properties={
                "_id": rounds_table.c.id,
                "_competition_id": rounds_table.c.competition_id,
                "_golf_course_id": rounds_table.c.golf_course_id,
                "_round_date": rounds_table.c.round_date,
                # Enum columns: TypeDecorators convierten string <-> enum
                "_session_type": rounds_table.c.session_type,
                "_match_format": rounds_table.c.match_format,
                "_status": rounds_table.c.status,
                "_handicap_mode": rounds_table.c.handicap_mode,
                "_allowance_percentage": rounds_table.c.allowance_percentage,
                "_created_at": rounds_table.c.created_at,
                "_updated_at": rounds_table.c.updated_at,
            },
        )

    # Mapear Match
    if Match not in mapper_registry.mappers:
        mapper_registry.map_imperatively(
            Match,
            matches_table,
            properties={
                "_id": matches_table.c.id,
                "_round_id": matches_table.c.round_id,
                "_match_number": matches_table.c.match_number,
                "_team_a_players": matches_table.c.team_a_players,
                "_team_b_players": matches_table.c.team_b_players,
                "_status": matches_table.c.status,
                "_handicap_strokes_given": matches_table.c.handicap_strokes_given,
                "_strokes_given_to_team": matches_table.c.strokes_given_to_team,
                "_result": matches_table.c.result,
                "_created_at": matches_table.c.created_at,
                "_updated_at": matches_table.c.updated_at,
            },
        )

    # Mapear TeamAssignment (Entity)
    if TeamAssignmentEntity not in mapper_registry.mappers:
        mapper_registry.map_imperatively(
            TeamAssignmentEntity,
            team_assignments_table,
            properties={
                "_id": team_assignments_table.c.id,
                "_competition_id": team_assignments_table.c.competition_id,
                "_mode": team_assignments_table.c.mode,
                "_team_a_player_ids": team_assignments_table.c.team_a_player_ids,
                "_team_b_player_ids": team_assignments_table.c.team_b_player_ids,
                "_created_at": team_assignments_table.c.created_at,
            },
        )


def start_mappers():
    """
    Inicia todos los mappers del Competition Module.

    Es idempotente: puede llamarse multiples veces sin efectos adversos.
    """
    start_competition_mappers()
