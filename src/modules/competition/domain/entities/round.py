"""
Round Entity - Sesión de competición.

Representa una sesión de partidos (mañana/tarde/noche) en un día específico.
"""

from datetime import UTC, date, datetime

from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.handicap_mode import HandicapMode
from src.modules.competition.domain.value_objects.match_format import MatchFormat
from src.modules.competition.domain.value_objects.round_id import RoundId
from src.modules.competition.domain.value_objects.round_status import RoundStatus
from src.modules.competition.domain.value_objects.session_type import SessionType
from src.modules.golf_course.domain.value_objects.golf_course_id import GolfCourseId

# Porcentajes de allowance permitidos (50-100 en incrementos de 5)
ALLOWED_PERCENTAGES = frozenset(range(50, 101, 5))  # {50, 55, 60, ..., 95, 100}

# Allowances por defecto según WHS (Ryder Cup = Match Play)
SINGLES_ALLOWANCE: int = 100  # Match Play
FOURBALL_ALLOWANCE: int = 90
FOURSOMES_ALLOWANCE: int = 50  # Se aplica a la DIFERENCIA entre equipos


class Round:
    """
    Entidad que representa una sesión de competición.

    Una sesión agrupa partidos que se juegan en un momento específico del día.
    Un día puede tener hasta 3 sesiones (MORNING, AFTERNOON, EVENING).
    Cada sesión puede jugarse en un campo diferente.

    Nota: Los tees NO se definen a nivel de Round. Cada jugador tiene su
    tee asignado en su Enrollment.

    Características DDD:
    - Es una Entity (tiene identidad: RoundId)
    - Vive dentro del contexto de Competition
    - Contiene Matches (pero no los gestiona directamente)
    """

    def __init__(
        self,
        id: RoundId,
        competition_id: CompetitionId,
        golf_course_id: GolfCourseId,
        round_date: date,
        session_type: SessionType,
        match_format: MatchFormat,
        status: RoundStatus,
        handicap_mode: HandicapMode | None,
        allowance_percentage: int | None,
        created_at: datetime,
        updated_at: datetime,
    ):
        """Constructor privado (usar factory methods)."""
        self._id = id
        self._competition_id = competition_id
        self._golf_course_id = golf_course_id
        self._round_date = round_date
        self._session_type = session_type
        self._match_format = match_format
        self._status = status
        self._handicap_mode = handicap_mode
        self._allowance_percentage = allowance_percentage
        self._created_at = created_at
        self._updated_at = updated_at

    @classmethod
    def create(
        cls,
        competition_id: CompetitionId,
        golf_course_id: GolfCourseId,
        round_date: date,
        session_type: SessionType,
        match_format: MatchFormat,
        handicap_mode: HandicapMode | None = None,
        allowance_percentage: int | None = None,
    ) -> "Round":
        """
        Factory method para crear una nueva sesión.

        Args:
            competition_id: ID de la competición
            golf_course_id: ID del campo de golf
            round_date: Fecha de la sesión
            session_type: Tipo de sesión (MORNING/AFTERNOON/EVENING)
            match_format: Formato de partido (SINGLES/FOURBALL/FOURSOMES)
            handicap_mode: Modo de handicap para SINGLES (MATCH_PLAY).
                           Ignorado para FOURBALL/FOURSOMES.
            allowance_percentage: Porcentaje de allowance personalizado (50-100, en incrementos de 5).
                                   Si None, usa defaults WHS según formato.

        Returns:
            Nueva instancia de Round con status PENDING_TEAMS

        Raises:
            ValueError: Si allowance_percentage fuera del rango válido
        """
        # Validar allowance_percentage si se proporciona (50-100 en incrementos de 5)
        if allowance_percentage is not None and allowance_percentage not in ALLOWED_PERCENTAGES:
            raise ValueError(
                f"allowance_percentage must be one of {sorted(ALLOWED_PERCENTAGES)}, "
                f"got {allowance_percentage}"
            )

        # Para SINGLES, si no se especifica handicap_mode, usar MATCH_PLAY por defecto
        effective_handicap_mode = handicap_mode
        if match_format == MatchFormat.SINGLES and handicap_mode is None:
            effective_handicap_mode = HandicapMode.MATCH_PLAY

        # Para formatos no-SINGLES, ignorar handicap_mode
        if match_format != MatchFormat.SINGLES:
            effective_handicap_mode = None

        now = datetime.now(UTC).replace(tzinfo=None)
        return cls(
            id=RoundId.generate(),
            competition_id=competition_id,
            golf_course_id=golf_course_id,
            round_date=round_date,
            session_type=session_type,
            match_format=match_format,
            status=RoundStatus.PENDING_TEAMS,
            handicap_mode=effective_handicap_mode,
            allowance_percentage=allowance_percentage,
            created_at=now,
            updated_at=now,
        )

    @classmethod
    def reconstruct(
        cls,
        id: RoundId,
        competition_id: CompetitionId,
        golf_course_id: GolfCourseId,
        round_date: date,
        session_type: SessionType,
        match_format: MatchFormat,
        status: RoundStatus,
        handicap_mode: HandicapMode | None,
        allowance_percentage: int | None,
        created_at: datetime,
        updated_at: datetime,
    ) -> "Round":
        """Reconstruye desde BD (sin validaciones)."""
        return cls(
            id=id,
            competition_id=competition_id,
            golf_course_id=golf_course_id,
            round_date=round_date,
            session_type=session_type,
            match_format=match_format,
            status=status,
            handicap_mode=handicap_mode,
            allowance_percentage=allowance_percentage,
            created_at=created_at,
            updated_at=updated_at,
        )

    # ==================== Business Methods ====================

    def mark_teams_assigned(self) -> None:
        """
        Marca que los equipos han sido asignados.
        Transición: PENDING_TEAMS → PENDING_MATCHES
        """
        if self._status != RoundStatus.PENDING_TEAMS:
            raise ValueError(
                f"Cannot mark teams assigned from status {self._status}. Expected PENDING_TEAMS"
            )
        self._status = RoundStatus.PENDING_MATCHES
        self._updated_at = datetime.now(UTC).replace(tzinfo=None)

    def mark_matches_generated(self) -> None:
        """
        Marca que los partidos han sido generados.
        Transición: PENDING_MATCHES → SCHEDULED
        """
        if self._status != RoundStatus.PENDING_MATCHES:
            raise ValueError(
                f"Cannot mark matches generated from status {self._status}. "
                f"Expected PENDING_MATCHES"
            )
        self._status = RoundStatus.SCHEDULED
        self._updated_at = datetime.now(UTC).replace(tzinfo=None)

    def start(self) -> None:
        """
        Inicia la sesión (al menos un partido comenzó).
        Transición: SCHEDULED → IN_PROGRESS
        """
        if self._status != RoundStatus.SCHEDULED:
            raise ValueError(f"Cannot start round from status {self._status}. Expected SCHEDULED")
        self._status = RoundStatus.IN_PROGRESS
        self._updated_at = datetime.now(UTC).replace(tzinfo=None)

    def complete(self) -> None:
        """
        Marca la sesión como completada.
        Transición: IN_PROGRESS → COMPLETED
        """
        if self._status != RoundStatus.IN_PROGRESS:
            raise ValueError(
                f"Cannot complete round from status {self._status}. Expected IN_PROGRESS"
            )
        self._status = RoundStatus.COMPLETED
        self._updated_at = datetime.now(UTC).replace(tzinfo=None)

    def update_details(
        self,
        round_date: date | None = None,
        session_type: SessionType | None = None,
        golf_course_id: GolfCourseId | None = None,
        match_format: MatchFormat | None = None,
        handicap_mode: HandicapMode | None = None,
        allowance_percentage: int | None = None,
        clear_allowance: bool = False,
    ) -> None:
        """
        Actualiza detalles de la sesión (solo si es modificable).

        Args:
            round_date: Nueva fecha de la sesión
            session_type: Nuevo tipo de sesión
            golf_course_id: Nuevo campo de golf
            match_format: Nuevo formato de partido
            handicap_mode: Nuevo modo de handicap (solo para SINGLES)
            allowance_percentage: Nuevo porcentaje de allowance (50-100, en incrementos de 5)
            clear_allowance: Si True, vuelve al allowance por defecto WHS

        Raises:
            ValueError: Si la sesión no puede modificarse o allowance inválido
        """
        if not self._status.can_modify():
            raise ValueError(
                f"Cannot modify round in status {self._status}. "
                f"Only PENDING_TEAMS or PENDING_MATCHES allowed"
            )

        if round_date is not None:
            self._round_date = round_date
        if session_type is not None:
            self._session_type = session_type
        if golf_course_id is not None:
            self._golf_course_id = golf_course_id

        # Actualizar formato y ajustar handicap_mode si es necesario
        if match_format is not None:
            self._match_format = match_format
            # Si cambia a no-SINGLES, limpiar handicap_mode
            if match_format != MatchFormat.SINGLES:
                self._handicap_mode = None
            # Si cambia a SINGLES y no tiene handicap_mode, poner default
            elif self._handicap_mode is None:
                self._handicap_mode = HandicapMode.MATCH_PLAY

        # Actualizar handicap_mode (solo tiene efecto para SINGLES)
        if handicap_mode is not None and self._match_format == MatchFormat.SINGLES:
            self._handicap_mode = handicap_mode

        # Actualizar allowance_percentage (50-100 en incrementos de 5)
        if clear_allowance:
            self._allowance_percentage = None
        elif allowance_percentage is not None:
            if allowance_percentage not in ALLOWED_PERCENTAGES:
                raise ValueError(
                    f"allowance_percentage must be one of {sorted(ALLOWED_PERCENTAGES)}, "
                    f"got {allowance_percentage}"
                )
            self._allowance_percentage = allowance_percentage

        self._updated_at = datetime.now(UTC).replace(tzinfo=None)

    # ==================== Query Methods ====================

    def players_per_match(self) -> int:
        """Retorna el número total de jugadores por partido según el formato."""
        return self._match_format.players_per_team() * 2

    def players_per_team_in_match(self) -> int:
        """Retorna el número de jugadores por equipo en cada partido."""
        return self._match_format.players_per_team()

    def can_generate_matches(self) -> bool:
        """Retorna True si se pueden generar partidos."""
        return self._status.can_generate_matches()

    def can_modify(self) -> bool:
        """Retorna True si la sesión puede modificarse."""
        return self._status.can_modify()

    def get_effective_allowance(self) -> int:
        """
        Retorna el porcentaje de allowance efectivo para cálculo de handicap.

        Si se configuró un allowance_percentage personalizado, lo retorna.
        Si no, retorna el valor por defecto según WHS:
        - SINGLES: 100% (Match Play)
        - FOURBALL: 90%
        - FOURSOMES: 50% (aplicado a la DIFERENCIA entre equipos)

        Returns:
            Porcentaje de allowance (1-100)
        """
        if self._allowance_percentage is not None:
            return self._allowance_percentage

        if self._match_format == MatchFormat.SINGLES:
            return SINGLES_ALLOWANCE

        if self._match_format == MatchFormat.FOURBALL:
            return FOURBALL_ALLOWANCE

        return FOURSOMES_ALLOWANCE

    # ==================== Properties ====================

    @property
    def id(self) -> RoundId:
        return self._id

    @property
    def competition_id(self) -> CompetitionId:
        return self._competition_id

    @property
    def golf_course_id(self) -> GolfCourseId:
        return self._golf_course_id

    @property
    def round_date(self) -> date:
        return self._round_date

    @property
    def session_type(self) -> SessionType:
        return self._session_type

    @property
    def match_format(self) -> MatchFormat:
        return self._match_format

    @property
    def status(self) -> RoundStatus:
        return self._status

    @property
    def created_at(self) -> datetime:
        return self._created_at

    @property
    def updated_at(self) -> datetime:
        return self._updated_at

    @property
    def handicap_mode(self) -> HandicapMode | None:
        """Modo de handicap (solo para SINGLES: MATCH_PLAY)."""
        return self._handicap_mode

    @property
    def allowance_percentage(self) -> int | None:
        """Porcentaje de allowance personalizado (None usa default WHS)."""
        return self._allowance_percentage

    # ==================== Equality ====================

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Round):
            return False
        return self._id == other._id

    def __hash__(self) -> int:
        return hash(self._id)

    def __repr__(self) -> str:
        return (
            f"Round(id={self._id}, "
            f"date={self._round_date}, "
            f"session={self._session_type}, "
            f"format={self._match_format}, "
            f"status={self._status})"
        )
