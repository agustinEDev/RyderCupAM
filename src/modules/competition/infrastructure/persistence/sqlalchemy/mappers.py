"""
Competition Module Mappers - SQLAlchemy Imperative Mapping.

Mapea las entidades del dominio de Competition a las tablas de PostgreSQL.
Sigue el patron Imperative Mapping establecido en el modulo User.
"""

import uuid
from datetime import date, time
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    Date,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    Numeric,
    String,
    Table,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import composite, relationship
from sqlalchemy.types import CHAR, TypeDecorator

# Domain Entities
from src.modules.competition.domain.entities.competition import (
    DEFAULT_MAX_PLAYERS,
    Competition,
)
from src.modules.competition.domain.entities.competition_golf_course import (
    CompetitionGolfCourse,
)
from src.modules.competition.domain.entities.draft import Draft, DraftPick
from src.modules.competition.domain.entities.enrollment import Enrollment
from src.modules.competition.domain.entities.envelope import Envelope
from src.modules.competition.domain.entities.hole_score import HoleScore
from src.modules.competition.domain.entities.invitation import Invitation
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
from src.modules.competition.domain.value_objects.draft_id import DraftId
from src.modules.competition.domain.value_objects.draft_status import DraftStatus
from src.modules.competition.domain.value_objects.enrollment_id import EnrollmentId
from src.modules.competition.domain.value_objects.enrollment_status import (
    EnrollmentStatus,
)
from src.modules.competition.domain.value_objects.envelope_id import EnvelopeId
from src.modules.competition.domain.value_objects.handicap_mode import HandicapMode
from src.modules.competition.domain.value_objects.hoja_de_salidas import HojaDeSalidas
from src.modules.competition.domain.value_objects.hole_score_id import HoleScoreId
from src.modules.competition.domain.value_objects.invitation_id import InvitationId
from src.modules.competition.domain.value_objects.invitation_status import InvitationStatus
from src.modules.competition.domain.value_objects.location import Location
from src.modules.competition.domain.value_objects.marker_assignment import MarkerAssignment
from src.modules.competition.domain.value_objects.match_generation_block import (
    MatchGenerationBlock,
)
from src.modules.competition.domain.value_objects.match_id import MatchId
from src.modules.competition.domain.value_objects.match_player import MatchPlayer
from src.modules.competition.domain.value_objects.match_status import MatchStatus
from src.modules.competition.domain.value_objects.round_id import RoundId
from src.modules.competition.domain.value_objects.round_status import RoundStatus
from src.modules.competition.domain.value_objects.ryder_cup_setup import RyderCupSetup
from src.modules.competition.domain.value_objects.session_type import SessionType
from src.modules.competition.domain.value_objects.setup_mode import SetupMode
from src.modules.competition.domain.value_objects.stroke_play_setup import StrokePlaySetup
from src.modules.competition.domain.value_objects.team_assignment_id import (
    TeamAssignmentId,
)
from src.modules.competition.domain.value_objects.team_assignment_mode import (
    TeamAssignmentMode,
)
from src.modules.competition.domain.value_objects.tournament_type import TournamentType
from src.modules.competition.domain.value_objects.validation_status import ValidationStatus
from src.modules.competition.domain.value_objects.visibility import Visibility

# Golf Course Entity and Value Object (FK)
from src.modules.golf_course.domain.entities.golf_course import GolfCourse
from src.modules.golf_course.domain.value_objects.golf_course_id import GolfCourseId
from src.modules.golf_course.domain.value_objects.tee_color import TeeColor

# User Value Object (FK)
from src.modules.user.domain.value_objects.user_id import UserId

# Shared Value Objects
from src.shared.domain.value_objects.country_code import CountryCode
from src.shared.domain.value_objects.gender import Gender
from src.shared.domain.value_objects.match_format import MatchFormat
from src.shared.domain.value_objects.play_mode import PlayMode

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


class InvitationIdDecorator(TypeDecorator):
    """TypeDecorator para convertir InvitationId (UUID VO) a/desde VARCHAR(36)."""

    impl = CHAR(36)
    cache_ok = True

    def process_bind_param(self, value: InvitationId | str | None, dialect) -> str | None:
        if isinstance(value, InvitationId):
            return str(value.value)
        if isinstance(value, str):
            return value
        return None

    def process_result_value(self, value: str | None, dialect) -> InvitationId | None:
        if value is None:
            return None
        return InvitationId(uuid.UUID(value))


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


class HoleScoreIdDecorator(TypeDecorator):
    """TypeDecorator para convertir HoleScoreId (UUID VO) a/desde VARCHAR(36)."""

    impl = CHAR(36)
    cache_ok = True

    def process_bind_param(self, value: HoleScoreId | str | None, dialect) -> str | None:
        if isinstance(value, HoleScoreId):
            return str(value.value)
        if isinstance(value, str):
            return value
        return None

    def process_result_value(self, value: str | None, dialect) -> HoleScoreId | None:
        if value is None:
            return None
        return HoleScoreId(uuid.UUID(value))


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


class DraftIdDecorator(TypeDecorator):
    """TypeDecorator para convertir DraftId (UUID VO) a/desde VARCHAR(36)."""

    impl = CHAR(36)
    cache_ok = True

    def process_bind_param(self, value: "DraftId | str | None", dialect) -> str | None:
        if isinstance(value, DraftId):
            return str(value.value)
        if isinstance(value, str):
            return value
        return None

    def process_result_value(self, value: str | None, dialect) -> "DraftId | None":
        if value is None:
            return None
        return DraftId(uuid.UUID(value))


class EnvelopeIdDecorator(TypeDecorator):
    """TypeDecorator para convertir EnvelopeId (UUID VO) a/desde VARCHAR(36)."""

    impl = CHAR(36)
    cache_ok = True

    def process_bind_param(self, value: "EnvelopeId | str | None", dialect) -> str | None:
        if isinstance(value, EnvelopeId):
            return str(value.value)
        if isinstance(value, str):
            return value
        return None

    def process_result_value(self, value: str | None, dialect) -> "EnvelopeId | None":
        if value is None:
            return None
        return EnvelopeId(uuid.UUID(value))


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
TeeColorDecorator = _create_enum_decorator(TeeColor)
PlayModeDecorator = _create_enum_decorator(PlayMode)
VisibilityDecorator = _create_enum_decorator(Visibility)
SetupModeDecorator = _create_enum_decorator(SetupMode)
TournamentTypeDecorator = _create_enum_decorator(TournamentType)
InvitationStatusDecorator = _create_enum_decorator(InvitationStatus)
ValidationStatusDecorator = _create_enum_decorator(ValidationStatus)
GenderDecorator = _create_enum_decorator(Gender)


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
        "tee_color": "YELLOW",
        "tee_gender": "MALE",
        "strokes_received": [1, 3, 5, 7],
        "player_handicap": "14.2"
    }

    player_handicap (HM-1b) es opcional: partidos generados antes de esta feature
    no lo tienen en su JSON y se deserializan con player_handicap=None.
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
                "tee_color": p.tee_color.value,
                "tee_gender": p.tee_gender.value if p.tee_gender else None,
                "strokes_received": list(p.strokes_received),
                "player_handicap": str(p.player_handicap)
                if p.player_handicap is not None
                else None,
            }
            for p in value
        ]

    def process_result_value(self, value: list | None, dialect) -> tuple | None:
        if value is None:
            return None
        players = []
        for p in value:
            player_handicap = p.get("player_handicap")
            player = MatchPlayer(
                user_id=UserId(uuid.UUID(p["user_id"])),
                playing_handicap=p["playing_handicap"],
                tee_color=TeeColor(p["tee_color"]),
                tee_gender=Gender(p["tee_gender"]) if p.get("tee_gender") else None,
                strokes_received=tuple(p["strokes_received"]),
                player_handicap=Decimal(player_handicap) if player_handicap is not None else None,
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


class DraftPicksJsonType(TypeDecorator):
    """TypeDecorator para las elecciones del draft, como array de objetos JSONB.

    En la misma fila que la sala y no en otra tabla: son pocas, siempre se leen
    juntas y nunca se consultan por separado, igual que los participantes de una
    partida rapida (FE #653).
    """

    impl = JSONB
    cache_ok = True

    def process_bind_param(self, value: tuple | list | None, dialect) -> list | None:
        if value is None:
            return None
        return [
            {
                "user_id": str(pick.user_id.value),
                "team": pick.team,
                "order": pick.order,
                "automatic": pick.automatic,
                "last_remaining": pick.last_remaining,
            }
            for pick in value
        ]

    def process_result_value(self, value: list | None, dialect) -> tuple | None:
        if value is None:
            return None
        return tuple(
            DraftPick(
                user_id=UserId(uuid.UUID(pick["user_id"])),
                team=pick["team"],
                order=pick["order"],
                automatic=pick.get("automatic", False),
                last_remaining=pick.get("last_remaining", False),
            )
            for pick in value
        )


class EnvelopeEntriesJsonType(TypeDecorator):
    """
    TypeDecorator para las filas de un sobre (FE #655).

    Se almacena como array de arrays de UUID: [["uuid-1"], ["uuid-2"], ...] en
    individuales, y [["uuid-1", "uuid-2"], ...] en los formatos de dos. Van en
    la misma fila del sobre porque el ORDEN es el dato: una tabla aparte
    obligaria a ordenar por una columna que no aporta nada mas.
    """

    impl = JSONB
    cache_ok = True

    def process_bind_param(self, value: tuple | list | None, dialect) -> list | None:
        if value is None:
            return None
        return [[str(uid.value) for uid in fila] for fila in value]

    def process_result_value(self, value: list | None, dialect) -> tuple | None:
        if value is None:
            return None
        return tuple(tuple(UserId(uuid.UUID(uid)) for uid in fila) for fila in value)


class MatchResultJsonType(TypeDecorator):
    """TypeDecorator pass-through para dict | None almacenado como JSONB."""

    impl = JSONB
    cache_ok = True

    def process_bind_param(self, value: dict | None, dialect) -> dict | None:
        return value

    def process_result_value(self, value: dict | None, dialect) -> dict | None:
        return value


class MatchGenerationBlockJsonType(TypeDecorator):
    """
    TypeDecorator para el motivo por el que una sesion no tiene partidos (BE #361).

    NULL en BD es «no hay motivo»: o se generaron, o nadie lo ha intentado.
    """

    impl = JSONB
    cache_ok = True

    def process_bind_param(self, value: MatchGenerationBlock | None, dialect) -> dict | None:
        return value.to_dict() if value is not None else None

    def process_result_value(self, value: dict | None, dialect) -> MatchGenerationBlock | None:
        return MatchGenerationBlock.from_dict(value) if value else None


class HojaDeSalidasJsonType(TypeDecorator):
    """
    TypeDecorator para la hoja de salidas de una franja de stroke play (#251).

    Una columna opcional: NULL en las sesiones de la Ryder. Las horas, en «HH:MM».
    """

    impl = JSONB
    cache_ok = True

    def process_bind_param(self, value: HojaDeSalidas | None, dialect) -> dict | None:
        """La hoja a JSON, con las horas en «HH:MM»."""
        if value is None:
            return None
        return {
            "first_tee_time": value.primera_salida.strftime("%H:%M"),
            "last_tee_time": value.ultima_salida.strftime("%H:%M"),
            "interval_minutes": value.intervalo_minutos,
            "group_size": value.jugadores_por_partida,
        }

    def process_result_value(self, value: dict | None, dialect) -> HojaDeSalidas | None:
        """El JSON a la hoja; NULL en las sesiones de la Ryder."""
        if not value:
            return None
        return HojaDeSalidas(
            primera_salida=time.fromisoformat(value["first_tee_time"]),
            ultima_salida=time.fromisoformat(value["last_tee_time"]),
            intervalo_minutos=value["interval_minutes"],
            jugadores_por_partida=value["group_size"],
        )


class MarkerAssignmentsJsonType(TypeDecorator):
    """
    TypeDecorator para serializar tuple[MarkerAssignment, ...] a/desde JSONB.

    Cada MarkerAssignment se serializa como:
    {
        "scorer_user_id": "uuid-string",
        "marks_user_id": "uuid-string",
        "marked_by_user_id": "uuid-string"
    }

    Retorna () (tupla vacia) para NULL en BD.
    """

    impl = JSONB
    cache_ok = True

    def process_bind_param(self, value: tuple | list | None, dialect) -> list | None:
        if not value:
            return None
        return [
            {
                "scorer_user_id": str(ma.scorer_user_id.value),
                "marks_user_id": str(ma.marks_user_id.value),
                "marked_by_user_id": str(ma.marked_by_user_id.value),
            }
            for ma in value
        ]

    def process_result_value(self, value: list | None, dialect) -> tuple:
        if not value:
            return ()
        return tuple(
            MarkerAssignment(
                scorer_user_id=UserId(uuid.UUID(ma["scorer_user_id"])),
                marks_user_id=UserId(uuid.UUID(ma["marks_user_id"])),
                marked_by_user_id=UserId(uuid.UUID(ma["marked_by_user_id"])),
            )
            for ma in value
        )


class ScorecardSubmittedByJsonType(TypeDecorator):
    """
    TypeDecorator para serializar tuple[UserId, ...] a/desde JSONB.

    Similar a UserIdsJsonType pero retorna () para NULL en BD
    (en vez de None), para coincidir con el default del Match entity.
    """

    impl = JSONB
    cache_ok = True

    def process_bind_param(self, value: tuple | list | None, dialect) -> list | None:
        if not value:
            return None
        return [str(uid.value) for uid in value]

    def process_result_value(self, value: list | None, dialect) -> tuple:
        if not value:
            return ()
        return tuple(UserId(uuid.UUID(uid_str)) for uid_str in value)


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
    # Lo de la Ryder Cup admite vacío: un Stableford o un Medal no tiene
    # equipos, ni modo de montaje, ni reparto (RyderCupAM#251)
    Column("team_1_name", String(100), nullable=True),
    Column("team_2_name", String(100), nullable=True),
    Column("play_mode", PlayModeDecorator, nullable=False),
    Column("max_players", Integer, nullable=False, default=DEFAULT_MAX_PLAYERS),
    Column("team_assignment", TeamAssignmentModeDecorator, nullable=True),
    Column("status", String(20), nullable=False, default="DRAFT"),
    Column("max_playing_handicap", Integer, nullable=True),
    # Hora LOCAL del campo donde se juega, sin huso a proposito: «las nueve» son
    # las nueve de alli, y la zona se resuelve al leerla (BE #319)
    Column("enrollment_opens_days_before", Integer, nullable=True),
    # Privada por defecto: lo que hay hoy son Ryders entre amigos, y publicar
    # el torneo de alguien sin querer no tiene vuelta atras (BE #318)
    Column("visibility", VisibilityDecorator, nullable=False, server_default="PRIVATE"),
    # Estilo RyderCup por defecto: es lo que son todas hoy (FE #695)
    Column("setup_mode", SetupModeDecorator, nullable=True),
    # Qué torneo es: de él sale la modalidad. Las de antes, todas Ryder Cup
    Column("tournament_type", TournamentTypeDecorator, nullable=False, server_default="RYDER_CUP"),
    # Lo que es solo del stroke play (6 oct 2026); vacío en una Ryder Cup
    Column("stroke_category_limits", ARRAY(Numeric(precision=4, scale=1)), nullable=True),
    Column("stroke_max_matchdays_per_player", Integer, nullable=True),
    Column("stroke_overall_standing", String(20), nullable=True),
    # Uno por equipo, y la baja de un usuario solo libera su puesto (BE #320)
    Column(
        "team_a_captain_id",
        UserIdDecorator,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    ),
    Column(
        "team_b_captain_id",
        UserIdDecorator,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    ),
    Column(
        "team_a_vice_captain_id",
        UserIdDecorator,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    ),
    Column(
        "team_b_vice_captain_id",
        UserIdDecorator,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    ),
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
    Column("tee_color", TeeColorDecorator, nullable=True),
    Column("use_real_name", Boolean, nullable=False, server_default="true"),
    # El hándicap de todo el torneo, fijado al cerrar las inscripciones (#251)
    Column("fixed_handicap", Numeric(precision=4, scale=1), nullable=True),
    Column("fixed_category", Integer, nullable=True),
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
    # Por que no se pudieron generar sus partidos al abrir los sobres (BE #361)
    Column("match_generation_block", MatchGenerationBlockJsonType, nullable=True),
    # La hoja de salidas de una franja de stroke play; NULL en la Ryder (#251)
    Column("tee_sheet", HojaDeSalidasJsonType, nullable=True),
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
    Column("marker_assignments", MarkerAssignmentsJsonType, nullable=True),
    Column("scorecard_submitted_by", ScorecardSubmittedByJsonType, nullable=True),
    Column("is_decided", Boolean, nullable=False, default=False),
    Column("decided_result", MatchResultJsonType, nullable=True),
    Column("created_at", DateTime, nullable=False),
    Column("updated_at", DateTime, nullable=False),
)


# =============================================================================
# TABLA TEAM_ASSIGNMENTS
# =============================================================================

DraftStatusDecorator = _create_enum_decorator(DraftStatus)

# =============================================================================
# TABLA DRAFTS (FE #653)
# =============================================================================

drafts_table = Table(
    "drafts",
    metadata,
    Column("id", DraftIdDecorator, primary_key=True),
    Column(
        "competition_id",
        CompetitionIdDecorator,
        ForeignKey("competitions.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    ),
    # RESTRICT: una sala sin capitan no existe, asi que borrar a uno con un
    # draft vivo se para antes, en el panel de administracion
    Column(
        "team_a_captain_id",
        UserIdDecorator,
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    ),
    Column(
        "team_b_captain_id",
        UserIdDecorator,
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    ),
    Column("status", DraftStatusDecorator, nullable=False),
    Column("first_pick", String(1), nullable=True),
    Column("current_team", String(1), nullable=True),
    # El reloj es del servidor: de aqui sale cuanto queda de turno (BE #305)
    Column("turn_started_at", DateTime, nullable=True),
    Column("picks", DraftPicksJsonType, nullable=False),
    Column("seconds_per_turn", Integer, nullable=False),
)


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
# TABLA ENVELOPES (FE #655)
# =============================================================================

envelopes_table = Table(
    "envelopes",
    metadata,
    Column("id", EnvelopeIdDecorator, primary_key=True),
    Column(
        "competition_id",
        CompetitionIdDecorator,
        ForeignKey("competitions.id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column(
        "round_id",
        RoundIdDecorator,
        ForeignKey("rounds.id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column("team", String(1), nullable=False),
    Column("match_format", MatchFormatDecorator, nullable=False),
    Column("entries", EnvelopeEntriesJsonType, nullable=False),
    Column("submitted_at", DateTime, nullable=True),
    # SET NULL y no CASCADE: si el capitan se borra, el sobre sigue valiendo.
    # Quien lo entrego es un dato de auditoria, no lo que hace valido el sobre
    Column(
        "submitted_by",
        UserIdDecorator,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    ),
    Column("automatic", Boolean, nullable=False, default=False),
    Column("revealed", Boolean, nullable=False, default=False),
    # Si ese capitan pidio abrirlos en cuanto esten los dos, sin esperar a la
    # hora. Hacen falta los DOS para que valga (23 sep)
    Column("reveal_when_both_ready", Boolean, nullable=False, default=False),
    # Uno por equipo y sesion: dos serian dos listas a la vez para el mismo
    # cruce, y nadie sabria cual manda
    UniqueConstraint("round_id", "team", name="uq_envelopes_round_team"),
)


# =============================================================================
# TABLA INVITATIONS
# =============================================================================

invitations_table = Table(
    "invitations",
    metadata,
    Column("id", InvitationIdDecorator, primary_key=True),
    Column(
        "competition_id",
        CompetitionIdDecorator,
        ForeignKey("competitions.id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column(
        "inviter_id",
        UserIdDecorator,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column("invitee_email", String(254), nullable=False),
    Column(
        "invitee_user_id",
        UserIdDecorator,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=True,
    ),
    Column("status", InvitationStatusDecorator, nullable=False),
    Column("personal_message", Text, nullable=True),
    Column("expires_at", DateTime, nullable=False),
    Column("responded_at", DateTime, nullable=True),
    Column("created_at", DateTime, nullable=False),
    Column("updated_at", DateTime, nullable=False),
)


# =============================================================================
# TABLA HOLE_SCORES
# =============================================================================

hole_scores_table = Table(
    "hole_scores",
    metadata,
    Column("id", HoleScoreIdDecorator, primary_key=True),
    Column(
        "match_id",
        MatchIdDecorator,
        ForeignKey("matches.id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column("hole_number", Integer, nullable=False),
    Column(
        "player_user_id",
        UserIdDecorator,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column("team", String(1), nullable=False),
    Column("own_score", Integer, nullable=True),
    Column("own_submitted", Boolean, nullable=False, default=False),
    Column("marker_score", Integer, nullable=True),
    Column("marker_submitted", Boolean, nullable=False, default=False),
    Column("strokes_received", Integer, nullable=False, default=0),
    Column("net_score", Integer, nullable=True),
    Column("validation_status", ValidationStatusDecorator, nullable=False),
    Column("created_at", DateTime, nullable=False),
    Column("updated_at", DateTime, nullable=False),
)


# Las actualizaciones de hándicaps con la RFEG de cada competición (#251).
# Sin entidad mapeada: las escribe y las lee su repositorio
handicap_updates_table = Table(
    "handicap_updates",
    metadata,
    Column("id", CHAR(36), primary_key=True),
    Column(
        "competition_id",
        CompetitionIdDecorator,
        ForeignKey("competitions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    ),
    Column("origin", String(30), nullable=False),
    Column("status", String(20), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("finished_at", DateTime(timezone=True), nullable=True),
    Column("resumed_at", DateTime(timezone=True), nullable=True),
)

# La plaza de cada jugador en cada franja de stroke play (#251). Sin entidad
# mapeada: la escribe y la lee su repositorio
tee_window_places_table = Table(
    "tee_window_places",
    metadata,
    Column("id", CHAR(36), primary_key=True),
    Column(
        "competition_id",
        CompetitionIdDecorator,
        ForeignKey("competitions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    ),
    Column(
        "round_id", RoundIdDecorator, ForeignKey("rounds.id", ondelete="CASCADE"), nullable=False
    ),
    Column("user_id", UserIdDecorator, ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    # Asignada por la lista de espera, y vista en «Requiere tu atención»
    Column("from_waiting_list_at", DateTime(timezone=True), nullable=True),
    Column("acknowledged_at", DateTime(timezone=True), nullable=True),
    UniqueConstraint("round_id", "user_id", name="uq_tee_window_places_round_user"),
    # «Requiere tu atención»: solo las asignadas por la lista y sin ver
    Index(
        "ix_tee_window_places_pending_ack",
        "user_id",
        postgresql_where=text("from_waiting_list_at IS NOT NULL AND acknowledged_at IS NULL"),
    ),
)

# La lista de espera de cada franja de stroke play (#251): el orden, el de llegada
tee_window_waits_table = Table(
    "tee_window_waits",
    metadata,
    Column("id", CHAR(36), primary_key=True),
    Column(
        "competition_id",
        CompetitionIdDecorator,
        ForeignKey("competitions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    ),
    Column(
        "round_id", RoundIdDecorator, ForeignKey("rounds.id", ondelete="CASCADE"), nullable=False
    ),
    Column("user_id", UserIdDecorator, ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    UniqueConstraint("round_id", "user_id", name="uq_tee_window_waits_round_user"),
)

# La actualización que deja programada el organizador: una por competición (#251)
handicap_update_schedules_table = Table(
    "handicap_update_schedules",
    metadata,
    Column(
        "competition_id",
        CompetitionIdDecorator,
        ForeignKey("competitions.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column("run_at", DateTime(timezone=True), nullable=False, index=True),
    Column("created_at", DateTime(timezone=True), nullable=False),
)

# Lo que contestó la RFEG por cada jugador en cada actualización, con los intentos
handicap_refreshes_table = Table(
    "handicap_refreshes",
    metadata,
    Column(
        "update_id",
        CHAR(36),
        ForeignKey("handicap_updates.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "user_id",
        UserIdDecorator,
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column("result", String(30), nullable=False),
    Column("attempts", Integer, nullable=False),
    Column("refreshed_at", DateTime(timezone=True), nullable=False),
)

# Las partidas de una franja de stroke play (#251, PR 4). La hora no se guarda:
# sale de la hoja de salidas por el número. Los únicos se comprueban al final de
# la transacción: un intercambio o un reordenado repite a medias un jugador o un
# número, y solo completo es válido.
tee_groups_table = Table(
    "tee_groups",
    metadata,
    Column("id", CHAR(36), primary_key=True),
    Column(
        "competition_id",
        CompetitionIdDecorator,
        ForeignKey("competitions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    ),
    Column(
        "round_id", RoundIdDecorator, ForeignKey("rounds.id", ondelete="CASCADE"), nullable=False
    ),
    Column("number", Integer, nullable=False),
    Column("status", String(20), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
    CheckConstraint("number >= 1", name="ck_tee_groups_number_positive"),
    UniqueConstraint(
        "round_id",
        "number",
        name="uq_tee_groups_round_number",
        deferrable=True,
        initially="DEFERRED",
    ),
    # Para que cada jugador lleve la franja de su partida (uno por franja)
    UniqueConstraint("id", "round_id", name="uq_tee_groups_id_round"),
)

# Cada jugador de una partida, con la foto que se sacó al generar (D14). Un
# usuario que juega no se puede borrar (RESTRICT): lo jugado no desaparece.
tee_group_players_table = Table(
    "tee_group_players",
    metadata,
    Column("group_id", CHAR(36), primary_key=True),
    Column("round_id", RoundIdDecorator, nullable=False),
    Column(
        "user_id",
        UserIdDecorator,
        ForeignKey("users.id", ondelete="RESTRICT"),
        primary_key=True,
        index=True,
    ),
    Column("position", Integer, nullable=False),
    Column("handicap_index", Numeric(precision=4, scale=1), nullable=False),
    Column("playing_handicap", Integer, nullable=False),
    Column("tee_color", TeeColorDecorator, nullable=False),
    Column("tee_gender", GenderDecorator, nullable=True),
    Column("strokes_by_hole", JSONB, nullable=False),
    Column(
        "marks_user_id", UserIdDecorator, ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    ),
    ForeignKeyConstraint(
        ["group_id", "round_id"],
        ["tee_groups.id", "tee_groups.round_id"],
        name="fk_tee_group_players_group",
        ondelete="CASCADE",
    ),
    UniqueConstraint(
        "round_id",
        "user_id",
        name="uq_tee_group_players_round_user",
        deferrable=True,
        initially="DEFERRED",
    ),
    UniqueConstraint(
        "group_id",
        "position",
        name="uq_tee_group_players_group_position",
        deferrable=True,
        initially="DEFERRED",
    ),
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
    - Invitation entity -> invitations table
    - HoleScore entity -> hole_scores table
    """
    # Mapear Competition
    if Competition not in mapper_registry.mappers:
        mapper_registry.map_imperatively(
            Competition,
            competitions_table,
            properties={
                # ID and scalar fields → private attrs
                "_id": competitions_table.c.id,
                "_creator_id": competitions_table.c.creator_id,
                "_play_mode": competitions_table.c.play_mode,
                "_max_players": competitions_table.c.max_players,
                "_max_playing_handicap": competitions_table.c.max_playing_handicap,
                "_enrollment_opens_days_before": competitions_table.c.enrollment_opens_days_before,
                "_visibility": competitions_table.c.visibility,
                "_tournament_type": competitions_table.c.tournament_type,
                # Lo que es solo de la Ryder Cup, en su pieza (RyderCupAM#251). Es
                # inmutable: SQLAlchemy no ve un cambio hecho dentro de un composite,
                # asi que la entidad la sustituye entera en cada cambio
                "_rc_team_1_name": competitions_table.c.team_1_name,
                "_rc_team_2_name": competitions_table.c.team_2_name,
                "_rc_setup_mode": competitions_table.c.setup_mode,
                "_rc_team_assignment": competitions_table.c.team_assignment,
                "_rc_team_a_captain_id": competitions_table.c.team_a_captain_id,
                "_rc_team_b_captain_id": competitions_table.c.team_b_captain_id,
                "_rc_team_a_vice_captain_id": competitions_table.c.team_a_vice_captain_id,
                "_rc_team_b_vice_captain_id": competitions_table.c.team_b_vice_captain_id,
                "_ryder_cup": composite(
                    RyderCupSetup.from_columns,
                    "_rc_team_1_name",
                    "_rc_team_2_name",
                    "_rc_setup_mode",
                    "_rc_team_assignment",
                    "_rc_team_a_captain_id",
                    "_rc_team_b_captain_id",
                    "_rc_team_a_vice_captain_id",
                    "_rc_team_b_vice_captain_id",
                ),
                # Y lo que es solo del stroke play, en la suya (6 oct 2026). Igual de
                # inmutable, por lo mismo
                "_sp_category_limits": competitions_table.c.stroke_category_limits,
                "_sp_max_matchdays_per_player": (
                    competitions_table.c.stroke_max_matchdays_per_player
                ),
                "_sp_overall_standing": competitions_table.c.stroke_overall_standing,
                "_stroke_play": composite(
                    StrokePlaySetup.from_columns,
                    "_sp_category_limits",
                    "_sp_max_matchdays_per_player",
                    "_sp_overall_standing",
                ),
                "_created_at": competitions_table.c.created_at,
                "_updated_at": competitions_table.c.updated_at,
                # Composite VOs → private attrs
                "_name_value": competitions_table.c.name,
                "_name": composite(lambda n: CompetitionName(n) if n else None, "_name_value"),
                "_start_date": competitions_table.c.start_date,
                "_end_date": competitions_table.c.end_date,
                "_dates": composite(
                    lambda s, e: DateRange(s, e) if s and e else None,
                    "_start_date",
                    "_end_date",
                ),
                "_country_code": competitions_table.c.country_code,
                "_secondary_country_code": competitions_table.c.secondary_country_code,
                "_tertiary_country_code": competitions_table.c.tertiary_country_code,
                "_location": composite(
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
                "_status_value": competitions_table.c.status,
                "_status": composite(
                    lambda s: CompetitionStatus(s) if s else CompetitionStatus.DRAFT,
                    "_status_value",
                ),
                # Relationships
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
                # Private attrs mapping
                "_id": enrollments_table.c.id,
                "_competition_id": enrollments_table.c.competition_id,
                "_user_id": enrollments_table.c.user_id,
                "_team_id": enrollments_table.c.team_id,
                "_custom_handicap": enrollments_table.c.custom_handicap,
                "_tee_color": enrollments_table.c.tee_color,
                "_use_real_name": enrollments_table.c.use_real_name,
                "_fixed_handicap": enrollments_table.c.fixed_handicap,
                "_fixed_category": enrollments_table.c.fixed_category,
                "_created_at": enrollments_table.c.created_at,
                "_updated_at": enrollments_table.c.updated_at,
                # Composite VOs → private attrs
                "_status_value": enrollments_table.c.status,
                "_status": composite(EnrollmentStatus, "_status_value"),
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
                "_match_generation_block": rounds_table.c.match_generation_block,
                "_hoja_de_salidas": rounds_table.c.tee_sheet,
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
                "_marker_assignments": matches_table.c.marker_assignments,
                "_scorecard_submitted_by": matches_table.c.scorecard_submitted_by,
                "_is_decided": matches_table.c.is_decided,
                "_decided_result": matches_table.c.decided_result,
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

    # Mapear Draft (FE #653)
    if Draft not in mapper_registry.mappers:
        mapper_registry.map_imperatively(
            Draft,
            drafts_table,
            properties={
                "_id": drafts_table.c.id,
                "_competition_id": drafts_table.c.competition_id,
                "_team_a_captain_id": drafts_table.c.team_a_captain_id,
                "_team_b_captain_id": drafts_table.c.team_b_captain_id,
                "_status": drafts_table.c.status,
                "_first_pick": drafts_table.c.first_pick,
                "_current_team": drafts_table.c.current_team,
                "_turn_started_at": drafts_table.c.turn_started_at,
                "_picks": drafts_table.c.picks,
                "_seconds_per_turn": drafts_table.c.seconds_per_turn,
            },
        )

    # Mapear Envelope (FE #655)
    if Envelope not in mapper_registry.mappers:
        mapper_registry.map_imperatively(
            Envelope,
            envelopes_table,
            properties={
                "_id": envelopes_table.c.id,
                "_competition_id": envelopes_table.c.competition_id,
                "_round_id": envelopes_table.c.round_id,
                "_team": envelopes_table.c.team,
                "_match_format": envelopes_table.c.match_format,
                "_entries": envelopes_table.c.entries,
                "_submitted_at": envelopes_table.c.submitted_at,
                "_submitted_by": envelopes_table.c.submitted_by,
                "_automatic": envelopes_table.c.automatic,
                "_revealed": envelopes_table.c.revealed,
                "_reveal_when_both_ready": envelopes_table.c.reveal_when_both_ready,
            },
        )

    # Mapear Invitation
    if Invitation not in mapper_registry.mappers:
        mapper_registry.map_imperatively(
            Invitation,
            invitations_table,
            properties={
                "_id": invitations_table.c.id,
                "_competition_id": invitations_table.c.competition_id,
                "_inviter_id": invitations_table.c.inviter_id,
                "_invitee_email": invitations_table.c.invitee_email,
                "_invitee_user_id": invitations_table.c.invitee_user_id,
                "_status": invitations_table.c.status,
                "_personal_message": invitations_table.c.personal_message,
                "_expires_at": invitations_table.c.expires_at,
                "_responded_at": invitations_table.c.responded_at,
                "_created_at": invitations_table.c.created_at,
                "_updated_at": invitations_table.c.updated_at,
            },
        )

    # Mapear HoleScore
    if HoleScore not in mapper_registry.mappers:
        mapper_registry.map_imperatively(
            HoleScore,
            hole_scores_table,
            properties={
                "_id": hole_scores_table.c.id,
                "_match_id": hole_scores_table.c.match_id,
                "_hole_number": hole_scores_table.c.hole_number,
                "_player_user_id": hole_scores_table.c.player_user_id,
                "_team": hole_scores_table.c.team,
                "_own_score": hole_scores_table.c.own_score,
                "_own_submitted": hole_scores_table.c.own_submitted,
                "_marker_score": hole_scores_table.c.marker_score,
                "_marker_submitted": hole_scores_table.c.marker_submitted,
                "_strokes_received": hole_scores_table.c.strokes_received,
                "_net_score": hole_scores_table.c.net_score,
                "_validation_status": hole_scores_table.c.validation_status,
                "_created_at": hole_scores_table.c.created_at,
                "_updated_at": hole_scores_table.c.updated_at,
            },
        )


def start_mappers():
    """
    Inicia todos los mappers del Competition Module.

    Es idempotente: puede llamarse multiples veces sin efectos adversos.
    """
    start_competition_mappers()
