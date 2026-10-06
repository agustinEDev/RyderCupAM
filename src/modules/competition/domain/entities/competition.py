"""
Competition Entity - Representa una competición/torneo de golf formato Ryder Cup.

Esta es el agregado raíz del módulo competition.
Gestiona el ciclo de vida completo del torneo y su configuración.
"""

from collections.abc import Collection, Sequence
from datetime import datetime
from decimal import Decimal

from src.modules.golf_course.domain.value_objects.golf_course_id import GolfCourseId
from src.modules.user.domain.value_objects.user_id import UserId
from src.shared.domain.events.domain_event import DomainEvent
from src.shared.domain.value_objects.country_code import CountryCode
from src.shared.domain.value_objects.modality import Modality
from src.shared.domain.value_objects.play_mode import PlayMode

from ..entities.competition_golf_course import CompetitionGolfCourse
from ..events.competition_activated_event import CompetitionActivatedEvent
from ..events.competition_cancelled_event import CompetitionCancelledEvent
from ..events.competition_completed_event import CompetitionCompletedEvent
from ..events.competition_created_event import CompetitionCreatedEvent
from ..events.competition_enrollments_closed_event import (
    CompetitionEnrollmentsClosedEvent,
)
from ..events.competition_enrollments_reopened_event import (
    CompetitionEnrollmentsReopenedEvent,
)
from ..events.competition_reverted_to_closed_event import (
    CompetitionRevertedToClosedEvent,
)
from ..events.competition_reverted_to_in_progress_event import (
    CompetitionRevertedToInProgressEvent,
)
from ..events.competition_started_event import CompetitionStartedEvent
from ..events.competition_updated_event import CompetitionUpdatedEvent
from ..services.enrollment_opening_service import EnrollmentOpeningService
from ..value_objects.competition_id import CompetitionId
from ..value_objects.competition_name import CompetitionName
from ..value_objects.competition_status import CompetitionStatus
from ..value_objects.date_range import DateRange
from ..value_objects.location import Location
from ..value_objects.overall_standing import OverallStanding
from ..value_objects.ryder_cup_setup import CaptainOnWrongTeamError, RyderCupSetup
from ..value_objects.setup_mode import SetupMode
from ..value_objects.stroke_play_setup import StrokePlaySetup
from ..value_objects.team_assignment import TeamAssignment
from ..value_objects.tournament_type import TournamentType
from ..value_objects.visibility import Visibility

# Constantes de validación
MIN_PLAYERS = 2
# 100 hasta que las inscripciones se paginen: hay seis consultas que piden como
# mucho 100 filas sin decirlo, así que una competición mayor se sortearía y se
# emparejaría con los 100 primeros. Subirlo a 300 va en su propia issue.
MAX_PLAYERS = 100
# 12: una Ryder entre amigos son 12 jugadores, y es lo que el formulario propone
DEFAULT_MAX_PLAYERS = 12

# Cuantos dias antes del torneo pueden abrirse solas las inscripciones (BE #332).
# Cero no es «antes» de nada, y dos semanas es el tope decidido el 21 sep: con
# mas antelacion la apertura deja de elegirse en una lista y se teclea.
MIN_ENROLLMENT_OPENING_DAYS = 1
MAX_ENROLLMENT_OPENING_DAYS = 14
MIN_PLAYING_HANDICAP = 1
MAX_PLAYING_HANDICAP = 54


class GolfCoursesOutsideLocationError(ValueError):
    """La ubicación nueva dejaría campos de la competición fuera de sus países."""

    pass


RYDER_SIN_STROKE_PLAY = (
    "Una Ryder Cup no tiene categorías, jornadas por jugador ni clasificación general de "
    "stroke play"
)


class TournamentTypeError(ValueError):
    """Se pide al torneo algo que su tipo no tiene: equipos a un Stableford (#251)."""

    pass


class CompetitionStateError(Exception):
    """Excepción lanzada cuando se intenta una operación en un estado inválido."""

    pass


class CaptainsLockedError(Exception):
    """Los capitanes ya no se pueden cambiar: los equipos estan repartidos."""

    pass


class CaptainNotEnrolledError(Exception):
    """El capitan propuesto no es un inscrito aprobado de la competicion."""

    pass


class TeamsNotAssignedError(Exception):
    """Todavia no hay equipos repartidos, y esto se elige dentro de un equipo."""

    pass


class Competition:
    """
    Entidad Competition - Representa un torneo de golf.

    Agregado raíz que gestiona:
    - Configuración del torneo (nombre, fechas, ubicación, modo de juego)
    - Equipos (nombres de los dos equipos)
    - Ciclo de vida (estados: DRAFT, ACTIVE, CLOSED, IN_PROGRESS, COMPLETED, CANCELLED)
    - Inscripciones (mediante agregado Enrollment)

    Invariantes:
    - El creador no puede ser None
    - El nombre debe ser válido
    - Las fechas deben ser un rango válido
    - Los nombres de equipos no pueden estar vacíos
    - max_players debe estar entre MIN_PLAYERS y MAX_PLAYERS
    - Solo se puede modificar configuración en estado DRAFT
    - Las transiciones de estado deben ser válidas

    Ejemplos:
        >>> from datetime import date
        >>> comp = Competition(
        ...     id=CompetitionId.generate(),
        ...     creator_id=UserId.generate(),
        ...     name=CompetitionName("Ryder Cup 2025"),
        ...     dates=DateRange(date(2025, 6, 1), date(2025, 6, 3)),
        ...     location=Location(CountryCode("ES")),
        ...     team_1_name="Europe",
        ...     team_2_name="USA",
        ...     play_mode=PlayMode.HANDICAP
        ... )
        >>> comp.status
        <CompetitionStatus.DRAFT: 'DRAFT'>
        >>> comp.activate()
        >>> comp.status
        <CompetitionStatus.ACTIVE: 'ACTIVE'>
    """

    def __init__(
        self,
        id: CompetitionId,
        creator_id: UserId,
        name: CompetitionName,
        dates: DateRange,
        location: Location,
        *,
        play_mode: PlayMode,
        team_1_name: str | None = None,
        team_2_name: str | None = None,
        max_players: int = DEFAULT_MAX_PLAYERS,
        team_assignment: TeamAssignment | None = None,
        status: CompetitionStatus = CompetitionStatus.DRAFT,
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
        domain_events: list[DomainEvent] | None = None,
        max_playing_handicap: int | None = None,
        enrollment_opens_days_before: int | None = None,
        visibility: Visibility = Visibility.PRIVATE,
        setup_mode: SetupMode | None = None,
        tournament_type: TournamentType = TournamentType.RYDER_CUP,
        category_limits: Sequence[Decimal] | None = None,
        max_matchdays_per_player: int | None = None,
        overall_standing: OverallStanding | None = None,
    ):
        # Validaciones de invariantes. Equipos, modo de montaje, reparto y
        # capitanes son de la Ryder Cup: viven en su pieza, y un torneo de otro
        # tipo no la tiene (RyderCupAM#251)
        self._tournament_type = tournament_type
        self._ryder_cup: RyderCupSetup | None = self._ryder_cup_for(
            tournament_type, team_1_name, team_2_name, setup_mode, team_assignment
        )
        # Y lo que es solo del stroke play, en la suya (6 oct 2026)
        self._stroke_play: StrokePlaySetup | None = self._stroke_play_for(
            tournament_type, category_limits, max_matchdays_per_player, overall_standing
        )
        if self._stroke_play is not None:
            self._stroke_play.check_fits_in(self._days_of(dates))
        self._validate_max_players(max_players)
        if max_playing_handicap is not None:
            self._validate_max_playing_handicap(max_playing_handicap)

        # Asignación de atributos privados (encapsulación)
        self._id = id
        self._creator_id = creator_id
        self._name = name
        self._dates = dates
        self._location = location
        self._play_mode = play_mode
        self._max_players = max_players
        self._max_playing_handicap = max_playing_handicap
        self._enrollment_opens_days_before = enrollment_opens_days_before
        self._visibility = visibility
        self._validate_enrollment_opening(enrollment_opens_days_before)
        self._status = status
        self._created_at = created_at or datetime.now()
        self._updated_at = updated_at or datetime.now()
        self._domain_events: list[DomainEvent] = domain_events or []
        self._golf_courses: list[CompetitionGolfCourse] = []

    @classmethod
    def create(
        cls,
        id: CompetitionId,
        creator_id: UserId,
        name: CompetitionName,
        dates: DateRange,
        location: Location,
        *,
        play_mode: PlayMode,
        team_1_name: str | None = None,
        team_2_name: str | None = None,
        max_players: int = DEFAULT_MAX_PLAYERS,
        team_assignment: TeamAssignment | None = None,
        max_playing_handicap: int | None = None,
        enrollment_opens_days_before: int | None = None,
        visibility: Visibility = Visibility.PRIVATE,
        setup_mode: SetupMode | None = None,
        tournament_type: TournamentType = TournamentType.RYDER_CUP,
        category_limits: Sequence[Decimal] | None = None,
        max_matchdays_per_player: int | None = None,
        overall_standing: OverallStanding | None = None,
    ) -> "Competition":
        """
        Factory method para crear una nueva competición.

        Crea la competición y emite el evento CompetitionCreatedEvent.
        """
        competition = cls(
            id=id,
            creator_id=creator_id,
            name=name,
            dates=dates,
            location=location,
            team_1_name=team_1_name,
            team_2_name=team_2_name,
            play_mode=play_mode,
            max_players=max_players,
            team_assignment=team_assignment,
            max_playing_handicap=max_playing_handicap,
            enrollment_opens_days_before=enrollment_opens_days_before,
            visibility=visibility,
            setup_mode=setup_mode,
            tournament_type=tournament_type,
            category_limits=category_limits,
            max_matchdays_per_player=max_matchdays_per_player,
            overall_standing=overall_standing,
            status=CompetitionStatus.DRAFT,
        )

        # Emitir evento de creación
        event = CompetitionCreatedEvent(
            competition_id=str(competition._id),
            creator_id=str(competition._creator_id),
            name=str(competition._name),
        )
        competition._add_domain_event(event)

        return competition

    @staticmethod
    def _ryder_cup_for(
        tournament_type: TournamentType,
        team_1_name: str | None,
        team_2_name: str | None,
        setup_mode: SetupMode | None,
        team_assignment: TeamAssignment | None,
    ) -> RyderCupSetup | None:
        """
        La pieza de la Ryder, o None si el tipo no tiene equipos.

        A un torneo sin equipos no se le tira en silencio lo que trae de ellos:
        quien los manda cree que existen, y se le dice por qué no.

        El reparto no se pasa a la pieza: sale del modo de montaje (FE #695).
        Se recibe solo para poder rechazarlo en un torneo sin equipos.
        """
        if tournament_type.has_teams:
            return RyderCupSetup.create(team_1_name, team_2_name, setup_mode or SetupMode.RYDER_CUP)
        if team_1_name is not None or team_2_name is not None or team_assignment is not None:
            raise TournamentTypeError(f"Un {tournament_type.label} no tiene equipos")
        if setup_mode is not None:
            raise TournamentTypeError(
                f"Un {tournament_type.label} no tiene modo de montaje: no hay partidos entre equipos"
            )
        return None

    @staticmethod
    def _stroke_play_for(
        tournament_type: TournamentType,
        category_limits: Sequence[Decimal] | None,
        max_matchdays_per_player: int | None,
        overall_standing: OverallStanding | None,
    ) -> StrokePlaySetup | None:
        """
        La pieza del stroke play, o None si el torneo es una Ryder.

        Como con los equipos al revés: a una Ryder no se le tira en silencio lo
        que trae de stroke play, se le dice por qué no.
        """
        if not tournament_type.has_teams:
            return StrokePlaySetup.create(
                category_limits, max_matchdays_per_player, overall_standing
            )
        if any(
            v is not None for v in (category_limits, max_matchdays_per_player, overall_standing)
        ):
            raise TournamentTypeError(RYDER_SIN_STROKE_PLAY)
        return None

    @staticmethod
    def _days_of(dates: DateRange) -> int:
        """Los días que dura el torneo, contando el primero y el último."""
        return dates.duration_days() + 1

    @staticmethod
    def _validate_max_players(max_players: int) -> None:
        """Valida que max_players esté en rango válido."""
        if not MIN_PLAYERS <= max_players <= MAX_PLAYERS:
            raise ValueError(f"max_players debe estar entre {MIN_PLAYERS} y {MAX_PLAYERS}")

    @staticmethod
    def _validate_max_playing_handicap(max_playing_handicap: int) -> None:
        """Valida que max_playing_handicap esté en rango válido (WHS: 1-54)."""
        if not MIN_PLAYING_HANDICAP <= max_playing_handicap <= MAX_PLAYING_HANDICAP:
            raise ValueError(
                f"max_playing_handicap debe estar entre "
                f"{MIN_PLAYING_HANDICAP} y {MAX_PLAYING_HANDICAP}"
            )

    # ===========================================
    # PROPERTIES (Encapsulación — solo lectura)
    # ===========================================

    @property
    def id(self) -> CompetitionId:
        return self._id

    @property
    def creator_id(self) -> UserId:
        return self._creator_id

    @property
    def name(self) -> CompetitionName:
        return self._name

    @property
    def dates(self) -> DateRange:
        return self._dates

    @property
    def location(self) -> Location:
        return self._location

    @property
    def tournament_type(self) -> TournamentType:
        return self._tournament_type

    @property
    def modality(self) -> Modality:
        """Se deriva del tipo: no existe un «stroke play + Ryder Cup»."""
        return self._tournament_type.modality

    @property
    def ryder_cup(self) -> RyderCupSetup | None:
        """Equipos, modo de montaje, reparto y capitanes: lo que es solo de la Ryder Cup."""
        return self._ryder_cup

    def require_ryder_cup(self) -> RyderCupSetup:
        """
        La pieza de la Ryder, para lo que solo existe en ella: equipos,
        capitanes, draft y sobres.

        Raises:
            TournamentTypeError: Si el torneo no tiene equipos
        """
        if self._ryder_cup is None:
            raise TournamentTypeError(f"Un {self._tournament_type.label} no tiene equipos")
        return self._ryder_cup

    @property
    def stroke_play(self) -> StrokePlaySetup | None:
        """Categorías, jornadas por jugador y regla de la general: solo del stroke play."""
        return self._stroke_play

    def update_stroke_play(
        self,
        category_limits: Sequence[Decimal] | None = None,
        max_matchdays_per_player: int | None = None,
        overall_standing: OverallStanding | None = None,
    ) -> StrokePlaySetup:
        """
        Cambia los ajustes del stroke play; None es «no lo toques».

        **Hasta que la competición empieza** (DRAFT, ACTIVE y CLOSED): al
        empezar se fija la categoría de cada jugador, y de ahí en adelante los
        límites ya no pueden moverse. Es la misma ventana que el hándicap
        personalizado, que es lo otro de lo que sale la categoría.

        Returns:
            Los ajustes como quedan

        Raises:
            TournamentTypeError: Si es una Ryder
            CompetitionStateError: Si ya ha empezado
            StrokePlaySettingsError: Si los ajustes no tienen sentido
        """
        if self._stroke_play is None:
            raise TournamentTypeError(RYDER_SIN_STROKE_PLAY)
        if not self._status.allows_handicap_edits():
            raise CompetitionStateError(
                "Los ajustes del stroke play se cambian hasta que empieza la competición"
            )
        nuevos = self._stroke_play.with_changes(
            category_limits, max_matchdays_per_player, overall_standing
        )
        nuevos.check_fits_in(self._days_of(self._dates))
        self._stroke_play = nuevos
        self._updated_at = datetime.now()
        return nuevos

    @property
    def play_mode(self) -> PlayMode:
        return self._play_mode

    @property
    def max_players(self) -> int:
        return self._max_players

    @property
    def max_playing_handicap(self) -> int | None:
        return self._max_playing_handicap

    @property
    def status(self) -> CompetitionStatus:
        return self._status

    @property
    def created_at(self) -> datetime:
        return self._created_at

    @property
    def updated_at(self) -> datetime:
        return self._updated_at

    # ===========================================
    # MÉTODOS DE CONSULTA (QUERIES)
    # ===========================================

    def is_creator(self, user_id: UserId) -> bool:
        """Verifica si un usuario es el creador del torneo."""
        return self._creator_id == user_id

    def is_draft(self) -> bool:
        """Verifica si el torneo está en borrador."""
        return self._status == CompetitionStatus.DRAFT

    def is_active(self) -> bool:
        """Verifica si el torneo está activo (inscripciones abiertas)."""
        return self._status == CompetitionStatus.ACTIVE

    def is_in_progress(self) -> bool:
        """Verifica si el torneo está en curso."""
        return self._status == CompetitionStatus.IN_PROGRESS

    def is_completed(self) -> bool:
        """Verifica si el torneo ha finalizado."""
        return self._status == CompetitionStatus.COMPLETED

    def is_cancelled(self) -> bool:
        """Verifica si el torneo fue cancelado."""
        return self._status == CompetitionStatus.CANCELLED

    def allows_enrollments(self) -> bool:
        """Verifica si el torneo permite inscripciones."""
        return self._status == CompetitionStatus.ACTIVE

    @property
    def enrollment_opens_days_before(self) -> int | None:
        """Cuantos dias antes del torneo se abren solas las inscripciones.

        `None` es lo normal: la mayoria de torneos nacen ya abiertos.
        """
        return self._enrollment_opens_days_before

    def _validate_enrollment_opening(self, dias: int | None) -> None:
        """Entre 1 y 14 dias antes, o nada.

        Abajo, cero dias no es «antes» de nada: para abrir ya, no se programa.
        Arriba, dos semanas es el tope que se decidio (21 sep): mas antelacion
        deja de elegirse en una lista y se teclea, y un torneo que abre
        inscripciones con meses de antelacion las abre a mano.
        """
        if dias is None:
            return

        if not MIN_ENROLLMENT_OPENING_DAYS <= dias <= MAX_ENROLLMENT_OPENING_DAYS:
            raise ValueError(
                f"Las inscripciones se abren entre {MIN_ENROLLMENT_OPENING_DAYS} y "
                f"{MAX_ENROLLMENT_OPENING_DAYS} días antes del torneo. Recibido: {dias}."
            )

    def schedule_enrollment_opening(self, dias: int | None) -> None:
        """Programa —o desprograma— la apertura de las inscripciones.

        `None` aqui significa QUITAR la fecha, no «dejala como esta»: quien se
        arrepiente de haberla puesto tiene que poder deshacerlo. Por eso no va
        en `update_info`, donde `None` es lo contrario (BE #319).
        """
        self._validate_enrollment_opening(dias)

        # Programar lo que ya esta abierto no significa nada, y aceptarlo en
        # silencio dejaba al organizador con un «abre en 5 dias» de vuelta en
        # cada lectura mientras la gente ya se apuntaba
        if dias is not None and self._status != CompetitionStatus.DRAFT:
            raise ValueError(
                "No se puede programar la apertura: las inscripciones ya están abiertas."
            )

        self._enrollment_opens_days_before = dias
        self._updated_at = datetime.now()

        # Quitar los dias es decir «abrela ya»: sin programacion no hay nada que
        # esperar, y dejarla en DRAFT la varaba sin salida (BE #332)
        if dias is None and self._status == CompetitionStatus.DRAFT:
            self.activate()

    @property
    def visibility(self) -> Visibility:
        """Quien puede ver esta competicion y pedir sitio en ella."""
        return self._visibility

    def accepts_enrollment_requests(self) -> bool:
        """Indica si un desconocido puede pedir plaza por su cuenta.

        En una privada se entra porque el organizador invita (BE #318).
        """
        return self._visibility.accepts_enrollment_requests()

    def allows_enrollment_opening(self) -> bool:
        """Indica si todavia esta por abrir, sin mirar la hora.

        Separado de `due_to_open` para poder descartar sin resolver la zona,
        que cuesta una consulta.
        """
        return self._status == CompetitionStatus.DRAFT

    def due_to_open(self, timezone: str | None) -> bool:
        """Indica si ya le toca abrirse, leyendo su hora en la zona del campo.

        Sin fecha, nunca: ahi manda la invitacion (BE #319a). Y solo un
        borrador se abre — una cancelada no resucita porque pase su hora, ni se
        reabre una que ya cerro inscripciones.

        La zona la pone el campo donde se juega, porque «las nueve» son las
        nueve de alli. Sin campo todavia no se abre sola: no se adivina.
        """
        if self._status != CompetitionStatus.DRAFT:
            return False
        return EnrollmentOpeningService.is_due(
            self._dates.start_date, self._enrollment_opens_days_before, timezone
        )

    def allows_modifications(self) -> bool:
        """Verifica si el torneo permite modificar configuración."""
        return self._status.allows_modifications()

    def allows_deletion(self, has_played: bool) -> bool:
        """Verifica si el torneo todavía se puede borrar del todo (BE #333, #347).

        Dos condiciones, y la segunda no se puede leer del estado. El estado
        tiene que permitirlo, y ademas **no puede haber nada jugado**: el estado
        se anda hacia atras —`revert-status` y `reopen-enrollments`— sin
        deshacer partidos ni golpes, asi que un torneo ya jugado puede volver a
        ACTIVE con sus tarjetas dentro. Mirando solo el estado, la cascada se
        las llevaria.

        Tener calendario o equipos sorteados no cuenta (21 y 22 sep): se protege
        lo jugado, no lo montado, y lo montado se rehace.

        Args:
            has_played: Si algun partido quedo terminado o con walkover, o
                alguien llego a anotar un hoyo.
        """
        return self._status.allows_deletion() and not has_played

    # ===========================================
    # MÉTODOS DE COMANDO (CAMBIOS DE ESTADO)
    # ===========================================

    def activate(self) -> None:
        """
        Activa el torneo (DRAFT → ACTIVE).

        Raises:
            CompetitionStateError: Si la transición no es válida
        """
        if not self._status.can_transition_to(CompetitionStatus.ACTIVE):
            raise CompetitionStateError(
                f"No se puede activar una competición en estado {self._status.value}"
            )

        self._status = CompetitionStatus.ACTIVE
        self._updated_at = datetime.now()

        # La apertura programada queda cumplida al abrir, venga de su hora, de
        # una invitacion o del boton. Conservarla haria que la ficha siguiera
        # anunciando «abre 5 dias antes» de algo que ya abrio (BE #332)
        self._enrollment_opens_days_before = None

        event = CompetitionActivatedEvent(
            competition_id=str(self._id),
            name=str(self._name),
            start_date=self._dates.start_date.isoformat(),
        )
        self._add_domain_event(event)

    def close_enrollments(self, total_enrollments: int = 0) -> None:
        """
        Cierra las inscripciones (ACTIVE → CLOSED).

        Raises:
            CompetitionStateError: Si la transición no es válida
        """
        if not self._status.can_transition_to(CompetitionStatus.CLOSED):
            raise CompetitionStateError(
                f"No se pueden cerrar inscripciones en estado {self._status.value}"
            )

        self._status = CompetitionStatus.CLOSED
        self._updated_at = datetime.now()

        event = CompetitionEnrollmentsClosedEvent(
            competition_id=str(self._id), total_enrollments=total_enrollments
        )
        self._add_domain_event(event)

    def start(self) -> None:
        """
        Inicia el torneo (CLOSED → IN_PROGRESS).

        Raises:
            CompetitionStateError: Si la transición no es válida
        """
        if not self._status.can_transition_to(CompetitionStatus.IN_PROGRESS):
            raise CompetitionStateError(
                f"No se puede iniciar una competición en estado {self._status.value}"
            )

        self._status = CompetitionStatus.IN_PROGRESS
        self._updated_at = datetime.now()

        event = CompetitionStartedEvent(competition_id=str(self._id), name=str(self._name))
        self._add_domain_event(event)

    def complete(self) -> None:
        """
        Finaliza el torneo (IN_PROGRESS → COMPLETED).

        Raises:
            CompetitionStateError: Si la transición no es válida
        """
        if not self._status.can_transition_to(CompetitionStatus.COMPLETED):
            raise CompetitionStateError(
                f"No se puede completar una competición en estado {self._status.value}"
            )

        self._status = CompetitionStatus.COMPLETED
        self._updated_at = datetime.now()

        event = CompetitionCompletedEvent(competition_id=str(self._id), name=str(self._name))
        self._add_domain_event(event)

    def cancel(self, reason: str | None = None) -> None:
        """
        Cancela el torneo (cualquier estado → CANCELLED).

        Raises:
            CompetitionStateError: Si ya está en estado final
        """
        if self._status.is_final():
            raise CompetitionStateError(
                f"No se puede cancelar una competición en estado final {self._status.value}"
            )

        if not self._status.can_transition_to(CompetitionStatus.CANCELLED):
            raise CompetitionStateError(f"No se puede cancelar desde estado {self._status.value}")

        self._status = CompetitionStatus.CANCELLED
        self._updated_at = datetime.now()

        event = CompetitionCancelledEvent(
            competition_id=str(self._id), name=str(self._name), reason=reason
        )
        self._add_domain_event(event)

    def revert_to_closed(self) -> None:
        """
        Revierte el torneo a CLOSED (IN_PROGRESS → CLOSED).

        Permite al creador corregir el schedule (equipos, rondas, matches)
        antes de reiniciar la competición.

        Raises:
            CompetitionStateError: Si la transición no es válida
        """
        if self._status != CompetitionStatus.IN_PROGRESS:
            raise CompetitionStateError(
                f"No se puede revertir a CLOSED desde estado {self._status.value}"
            )

        self._status = CompetitionStatus.CLOSED
        self._updated_at = datetime.now()

        event = CompetitionRevertedToClosedEvent(competition_id=str(self._id), name=str(self._name))
        self._add_domain_event(event)

    def revert_to_in_progress(self) -> None:
        """
        Revierte el torneo completado a IN_PROGRESS (COMPLETED → IN_PROGRESS).

        Permite al creador reabrir un torneo ya finalizado, por ejemplo para
        añadir una ronda adicional. No modifica rounds ni matches existentes:
        los partidos ya completados permanecen intactos.

        Raises:
            CompetitionStateError: Si la transición no es válida
        """
        if self._status != CompetitionStatus.COMPLETED:
            raise CompetitionStateError(
                f"No se puede revertir a IN_PROGRESS desde estado {self._status.value}"
            )

        self._status = CompetitionStatus.IN_PROGRESS
        self._updated_at = datetime.now()

        event = CompetitionRevertedToInProgressEvent(
            competition_id=str(self._id), name=str(self._name)
        )
        self._add_domain_event(event)

    # ===========================================
    # CAPITANES (BE #320)
    # ===========================================

    def name_captains(
        self,
        team_a: UserId,
        team_b: UserId,
        approved_player_ids: Collection[UserId],
        has_teams: bool,
    ) -> None:
        """Nombra a los dos capitanes, y con las inscripciones abiertas las cierra.

        Nadie quiere pulsar «cerrar inscripciones», pero nombrar a los capitanes
        si es algo que el organizador quiere hacer, y es lo que de verdad congela
        la plantilla (decidido el 20 sep). Ya cerradas, se pueden cambiar
        mientras no haya equipos: despues, cambiar uno exigiria rehacerlos.

        Los capitanes siempre juegan: tienen que ser dos de los inscritos
        aprobados, y el organizador puede ser uno si esta inscrito.

        Args:
            team_a: Capitan del equipo A
            team_b: Capitan del equipo B
            approved_player_ids: Los inscritos aprobados. Las inscripciones son
                otro agregado: el caso de uso los trae, y la regla vive aqui
            has_teams: Si ya hay equipos repartidos. Es otro agregado, y
                reabrir las inscripciones no lo deshace: por eso no se deduce
                del estado.

        Raises:
            ValueError: Si es la misma persona
            CaptainNotEnrolledError: Si alguno no es un inscrito aprobado
            CaptainsLockedError: Si ya hay equipos repartidos
            CompetitionStateError: Si no esta en ACTIVE ni en CLOSED
        """
        ryder_cup = self.require_ryder_cup()
        if team_a == team_b:
            raise ValueError("Los capitanes tienen que ser dos jugadores distintos")
        if team_a not in approved_player_ids or team_b not in approved_player_ids:
            raise CaptainNotEnrolledError(
                "Los capitanes tienen que ser jugadores inscritos y aprobados"
            )
        if self._status not in (CompetitionStatus.ACTIVE, CompetitionStatus.CLOSED):
            raise CompetitionStateError(
                f"Los capitanes se nombran con las inscripciones abiertas o recien "
                f"cerradas. Estado actual: {self._status.value}"
            )
        if has_teams:
            raise CaptainsLockedError(
                "Los equipos ya estan repartidos: cambiar un capitan obligaria a rehacerlos"
            )

        self._ryder_cup = ryder_cup.with_captains(team_a, team_b)
        if self._status == CompetitionStatus.ACTIVE:
            self.close_enrollments(total_enrollments=len(approved_player_ids))
        else:
            self._updated_at = datetime.now()

    def name_vice_captain(
        self,
        team: str,
        player: UserId,
        team_player_ids: Collection[UserId],
        has_teams: bool,
    ) -> None:
        """Nombra al subcapitan de un equipo, que asciende si el capitan se va.

        Decidido el 22 sep: lo elige cada capitan entre los de su equipo, una
        vez repartidos. Quien puede pedirlo (el capitan, el organizador o un
        admin) lo decide el caso de uso.

        Args:
            team: "A" o "B"
            player: El subcapitan
            team_player_ids: Los jugadores de ese equipo que siguen inscritos
            has_teams: Si ya hay equipos repartidos

        Raises:
            ValueError: Si el equipo no existe o es su propio capitan
            CompetitionStateError: Si no esta en ACTIVE ni en CLOSED
            TeamsNotAssignedError: Si todavia no hay equipos
            CaptainOnWrongTeamError: Si no es de ese equipo
        """
        ryder_cup = self._comprobar_dentro_del_equipo(team, player, team_player_ids, has_teams)
        if player == ryder_cup.captain(team):
            raise ValueError("El capitán no puede ser también su subcapitán")
        self._ryder_cup = ryder_cup.with_vice_captain(team, player)
        self._updated_at = datetime.now()

    def fill_captain(
        self,
        team: str,
        player: UserId,
        team_player_ids: Collection[UserId],
        has_teams: bool,
    ) -> None:
        """Cubre el puesto de un capitan que se fue sin subcapitan que ascendiera.

        Solo tras el draft —antes se nombran los dos con `name_captains`— y solo
        si el capitan ya no esta: el puesto vacio, o un capitan que ya no sigue
        en la plantilla. Lo segundo pasa si se retiro con el torneo en marcha,
        donde la baja no toca a los capitanes, y despues se volvio a CLOSED. Un
        capitan que sigue no se cambia por aqui: obligaria a rehacer los equipos.

        Raises:
            ValueError: Si el equipo no existe
            CompetitionStateError: Si no esta en ACTIVE ni en CLOSED
            TeamsNotAssignedError: Si todavia no hay equipos
            CaptainOnWrongTeamError: Si no es de ese equipo
            CaptainsLockedError: Si el capitan de ese equipo sigue en el torneo
        """
        ryder_cup = self._comprobar_dentro_del_equipo(team, player, team_player_ids, has_teams)
        if ryder_cup.captain(team) in team_player_ids:
            raise CaptainsLockedError(
                "Ese equipo ya tiene capitán: solo se cubre el puesto de uno que se fue"
            )
        # Si era el subcapitán de ese equipo, la pieza deja ese puesto libre
        self._ryder_cup = ryder_cup.with_captain(team, player)
        self._updated_at = datetime.now()

    def handle_withdrawal(self, user_id: UserId) -> bool:
        """Lo que pasa con los capitanes cuando un jugador se da de baja.

        La baja sigue funcionando como siempre (22 sep). Si se va un capitan,
        asciende su subcapitan; sin subcapitan, el puesto queda libre y el
        organizador lo cubre. Si se va un subcapitan, su puesto queda libre.

        Con el torneo en marcha o terminado no se toca nada: una baja ahi no
        puede borrar al capitan de un torneo que se esta jugando.

        Returns:
            True si era capitan o subcapitan y algo cambio
        """
        if self._ryder_cup is None:
            # Sin equipos no hay capitanes que ascender
            return False
        if self._status not in (CompetitionStatus.ACTIVE, CompetitionStatus.CLOSED):
            return False
        despues = self._ryder_cup.after_withdrawal(user_id)
        if despues is None:
            return False
        self._ryder_cup = despues
        self._updated_at = datetime.now()
        return True

    def teams_reassigned(self) -> None:
        """Al repartir de nuevo, los subcapitanes quedan libres.

        Se eligen entre los del equipo, y el equipo ha cambiado: el draft
        automatico puede haber movido a un subcapitan al otro lado.
        """
        self._ryder_cup = self.require_ryder_cup().without_vice_captains()

    def _comprobar_dentro_del_equipo(
        self,
        team: str,
        player: UserId,
        team_player_ids: Collection[UserId],
        has_teams: bool,
    ) -> RyderCupSetup:
        """Lo comun a elegir capitan o subcapitan dentro de un equipo ya repartido."""
        ryder_cup = self.require_ryder_cup()
        RyderCupSetup.check_team(team)
        if self._status not in (CompetitionStatus.ACTIVE, CompetitionStatus.CLOSED):
            raise CompetitionStateError(
                f"Con el torneo en marcha ya no se cambia. Estado actual: {self._status.value}"
            )
        if not has_teams:
            raise TeamsNotAssignedError(
                "Todavía no hay equipos: antes del reparto se nombran los dos capitanes"
            )
        if player not in team_player_ids:
            raise CaptainOnWrongTeamError(f"Tiene que ser un jugador del equipo {team}")
        return ryder_cup

    def reopen_enrollments(self) -> None:
        """
        Reabre las inscripciones (CLOSED → ACTIVE).

        Permite al creador añadir o modificar jugadores antes de
        volver a cerrar inscripciones y configurar el schedule.

        Raises:
            CompetitionStateError: Si la transición no es válida
        """
        if self._status != CompetitionStatus.CLOSED:
            raise CompetitionStateError(
                f"No se pueden reabrir inscripciones desde estado {self._status.value}"
            )

        self._status = CompetitionStatus.ACTIVE
        self._updated_at = datetime.now()

        event = CompetitionEnrollmentsReopenedEvent(
            competition_id=str(self._id), name=str(self._name)
        )
        self._add_domain_event(event)

    # ===========================================
    # MÉTODOS DE ACTUALIZACIÓN
    # ===========================================

    def update_info(
        self,
        name: CompetitionName | None = None,
        dates: DateRange | None = None,
        location: Location | None = None,
        team_1_name: str | None = None,
        team_2_name: str | None = None,
        play_mode: PlayMode | None = None,
        max_players: int | None = None,
        team_assignment: TeamAssignment | None = None,
        max_playing_handicap: int | None = None,
        visibility: Visibility | None = None,
        setup_mode: SetupMode | None = None,
        golf_course_countries: Collection[CountryCode] | None = None,
    ) -> None:
        """
        Actualiza la información del torneo, mientras las inscripciones estén abiertas.

        Al cambiar la location hacen falta los países de sus campos de golf: los
        campos son otro agregado, así que el caso de uso los trae y la regla vive
        aquí. Una location que deje fuera alguno se rechaza con el motivo, y los
        campos se quitan antes desde la ficha (Agustín, 3 oct 2026).

        Raises:
            CompetitionStateError: Si no está en estado DRAFT
            ValueError: Si los nuevos valores no son válidos
        """
        if not self.allows_modifications():
            raise CompetitionStateError(
                f"No se puede modificar la configuración en estado {self._status.value}. "
                f"Solo mientras las inscripciones están abiertas."
            )
        toca_la_ryder = any(
            v is not None for v in (team_1_name, team_2_name, team_assignment, setup_mode)
        )
        # Antes de cambiar nada: un Stableford con equipos se rechaza entero
        ryder_cup = self.require_ryder_cup() if toca_la_ryder else self._ryder_cup

        if name is not None:
            self._name = name

        if dates is not None and self._stroke_play is not None:
            # Antes de cambiar nada: acortar el torneo no puede dejar fuera
            # jornadas que un jugador tiene derecho a jugar
            self._stroke_play.check_fits_in(self._days_of(dates))

        if dates is not None:
            # Mover las fechas ya no puede invalidar la apertura: son dias de
            # antelacion, asi que la apertura se mueve CON el torneo. Eso es lo
            # que se buscaba al dejar de guardar el instante (BE #332)
            self._dates = dates

        if location is not None:
            self._comprobar_que_los_campos_siguen_dentro(location, golf_course_countries)
            self._location = location

        if play_mode is not None:
            self._play_mode = play_mode

        if max_players is not None:
            self._validate_max_players(max_players)
            self._max_players = max_players

        if team_assignment is not None and ryder_cup is not None:
            ryder_cup = ryder_cup.with_team_assignment(team_assignment)

        if max_playing_handicap is not None:
            self._validate_max_playing_handicap(max_playing_handicap)
            self._max_playing_handicap = max_playing_handicap

        if visibility is not None:
            self._visibility = visibility

        # Mientras las inscripciones sigan abiertas, que es lo que ya exige este
        # metodo: al cerrarlas el modo decide lo que ya esta montado (FE #695).
        # Ojo: por la API hay un limite mas estrecho —BE #323 rechaza la edicion
        # entera si ya hay rondas—, asi que una reabierta con calendario ya no
        # cambia de modo
        if setup_mode is not None and ryder_cup is not None:
            # El modo manda: si llegan los dos, el reparto sale de el
            ryder_cup = ryder_cup.with_setup_mode(setup_mode)

        if (team_1_name is not None or team_2_name is not None) and ryder_cup is not None:
            ryder_cup = ryder_cup.with_team_names(team_1_name, team_2_name)

        self._ryder_cup = ryder_cup

        self._updated_at = datetime.now()

        event = CompetitionUpdatedEvent(competition_id=str(self._id), name=str(self._name))
        self._add_domain_event(event)

    # ===========================================
    # DOMAIN EVENTS
    # ===========================================

    def _ensure_domain_events(self) -> None:
        """Asegura que _domain_events existe (para compatibilidad con SQLAlchemy)."""
        if not hasattr(self, "_domain_events"):
            self._domain_events = []

    def _add_domain_event(self, event: DomainEvent) -> None:
        """Añade un evento de dominio de forma segura."""
        self._ensure_domain_events()
        self._domain_events.append(event)

    def get_domain_events(self) -> list[DomainEvent]:
        """Obtiene los eventos de dominio pendientes."""
        self._ensure_domain_events()
        return self._domain_events.copy()

    def clear_domain_events(self) -> None:
        """Limpia los eventos de dominio después de procesarlos."""
        self._ensure_domain_events()
        self._domain_events.clear()

    # ===========================================
    # GOLF COURSE MANAGEMENT
    # ===========================================

    def add_golf_course(self, golf_course_id: GolfCourseId, country_code: CountryCode) -> None:
        """
        Añade un campo de golf a la competición.

        Business Rules:
        - Hasta que la competición termina o se cancela (BE #368)
        - El país del campo debe ser compatible con la location de la competición
        - No se permiten duplicados

        Raises:
            CompetitionStateError: Si la competición ya terminó o se canceló
            ValueError: Si el país no es compatible o el campo ya existe
        """
        if not self._status.allows_adding_golf_courses():
            raise CompetitionStateError(
                f"No se pueden añadir campos de golf a una competición terminada "
                f"o cancelada. Estado actual: {self._status.value}"
            )

        if not self._is_country_compatible(country_code):
            raise ValueError(
                f"El campo de golf está en {country_code.value}, "
                f"que no es compatible con la location de la competición: {self._location}"
            )

        if self.has_golf_course(golf_course_id):
            raise ValueError(f"El campo de golf {golf_course_id} ya está añadido a la competición")

        next_order = len(self._golf_courses) + 1

        association = CompetitionGolfCourse.create(
            competition_id=self._id,
            golf_course_id=golf_course_id,
            display_order=next_order,
        )

        self._golf_courses.append(association)
        self._updated_at = datetime.now()

    def remove_golf_course(self, golf_course_id: GolfCourseId) -> None:
        """
        Quita un campo de golf de la competición. Reordena automáticamente.

        Raises:
            CompetitionStateError: Si las inscripciones ya no están abiertas
            ValueError: Si el campo no existe
        """
        if not self.allows_modifications():
            raise CompetitionStateError(
                f"Solo puedes quitar campos de golf mientras las inscripciones "
                f"están abiertas. Estado actual: {self._status.value}"
            )

        sorted_golf_courses = sorted(self._golf_courses, key=lambda cgc: cgc.display_order)

        field_to_remove = None
        for cgc in sorted_golf_courses:
            if cgc.golf_course_id == golf_course_id:
                field_to_remove = cgc
                break

        if field_to_remove is None:
            raise ValueError(f"El campo de golf {golf_course_id} no está en la competición")

        sorted_golf_courses.remove(field_to_remove)
        self._golf_courses = sorted_golf_courses

        for i, cgc in enumerate(self._golf_courses, start=1):
            cgc.change_order(i)

        self._updated_at = datetime.now()

    def validate_reorder(self, golf_course_ids: list[GolfCourseId]) -> None:
        """
        Valida que una lista de golf_course_ids es válida para reordenar.

        Raises:
            CompetitionStateError: Si las inscripciones ya no están abiertas
            ValueError: Si los IDs no coinciden con los campos actuales
        """
        if not self.allows_modifications():
            raise CompetitionStateError(
                f"Solo puedes reordenar campos de golf mientras las inscripciones "
                f"están abiertas. Estado actual: {self._status.value}"
            )

        if len(golf_course_ids) != len(self._golf_courses):
            raise ValueError(
                f"Debes especificar el orden para todos los campos. "
                f"Esperados: {len(self._golf_courses)}, Recibidos: {len(golf_course_ids)}"
            )

        current_ids = {cgc.golf_course_id for cgc in self._golf_courses}
        new_ids = set(golf_course_ids)
        if current_ids != new_ids:
            raise ValueError(
                "La lista de IDs no coincide con los campos actuales de la competición"
            )

    def reorder_golf_courses_phase1(self, new_order: list[tuple[GolfCourseId, int]]) -> None:
        """
        Fase 1 de reordenación: asigna valores temporales altos para evitar
        violaciones de UNIQUE constraint en BD.

        Debe llamarse flush() entre phase1 y phase2.
        """
        for idx, (golf_course_id, _) in enumerate(new_order):
            for cgc in self._golf_courses:
                if cgc.golf_course_id == golf_course_id:
                    cgc.change_order(10000 + idx + 1)
                    break

    def reorder_golf_courses_phase2(self, new_order: list[tuple[GolfCourseId, int]]) -> None:
        """
        Fase 2 de reordenación: asigna los valores finales (1, 2, 3...).
        """
        for golf_course_id, new_display_order in new_order:
            for cgc in self._golf_courses:
                if cgc.golf_course_id == golf_course_id:
                    cgc.change_order(new_display_order)
                    break

        self._updated_at = datetime.now()

    def reorder_golf_courses(self, new_order: list[tuple[GolfCourseId, int]]) -> None:
        """
        Cambia el orden de los campos de golf (single-phase, for non-DB contexts).

        Raises:
            CompetitionStateError: Si las inscripciones ya no están abiertas
            ValueError: Si hay órdenes duplicados o no secuenciales
        """
        if not self.allows_modifications():
            raise CompetitionStateError(
                f"Solo puedes reordenar campos de golf mientras las inscripciones "
                f"están abiertas. Estado actual: {self._status.value}"
            )

        if len(new_order) != len(self._golf_courses):
            raise ValueError(
                f"Debes especificar el orden para todos los campos. "
                f"Esperados: {len(self._golf_courses)}, Recibidos: {len(new_order)}"
            )

        orders = [order for _, order in new_order]
        expected_orders = list(range(1, len(new_order) + 1))
        if sorted(orders) != expected_orders:
            raise ValueError(
                f"El orden debe ser secuencial (1, 2, 3...). Recibido: {sorted(orders)}"
            )

        for golf_course_id, new_display_order in new_order:
            for cgc in self._golf_courses:
                if cgc.golf_course_id == golf_course_id:
                    cgc.change_order(new_display_order)
                    break
            else:
                raise ValueError(f"Campo {golf_course_id} no encontrado")

        self._updated_at = datetime.now()

    def _is_country_compatible(self, country_code: CountryCode) -> bool:
        """Verifica si un país es compatible con la location de la competición."""
        return self._country_in(self._location, country_code)

    @staticmethod
    def _country_in(location: Location, country_code: CountryCode) -> bool:
        """Si un país es uno de los de esa location: el principal o un adyacente."""
        return country_code in (
            location.main_country,
            location.adjacent_country_1,
            location.adjacent_country_2,
        )

    def _comprobar_que_los_campos_siguen_dentro(
        self, location: Location, golf_course_countries: Collection[CountryCode] | None
    ) -> None:
        """
        Los campos tienen que seguir en los países de la competición.

        Raises:
            ValueError: Si no se dicen los países de los campos: sin ellos la
                comprobación se saltaría en silencio
            GolfCoursesOutsideLocationError: Si alguno queda fuera
        """
        if golf_course_countries is None:
            raise ValueError("Para cambiar la ubicación hacen falta los países de sus campos")
        fuera = sorted(
            {c.value for c in golf_course_countries if not self._country_in(location, c)}
        )
        if fuera:
            raise GolfCoursesOutsideLocationError(
                f"Quita antes desde la ficha los campos de {', '.join(fuera)}: "
                "quedarían fuera de los países de la competición"
            )

    def has_golf_course(self, golf_course_id: GolfCourseId) -> bool:
        """Verifica si un campo de golf ya está en la competición."""
        return any(cgc.golf_course_id == golf_course_id for cgc in self._golf_courses)

    @property
    def golf_courses(self) -> list[CompetitionGolfCourse]:
        """Retorna la lista de campos de golf (ordenados por display_order)."""
        return sorted(self._golf_courses, key=lambda cgc: cgc.display_order)

    # ===========================================
    # MÉTODOS ESPECIALES
    # ===========================================

    def __str__(self) -> str:
        """Representación string legible."""
        return f"{self._name} ({self._status.value})"

    def __eq__(self, other) -> bool:
        """Operador de igualdad - Comparación por identidad (ID)."""
        return isinstance(other, Competition) and self._id == other._id

    def __hash__(self) -> int:
        """Hash del objeto basado en el ID."""
        return hash(self._id)
