"""
Competition Entity - Representa una competición/torneo de golf formato Ryder Cup.

Esta es el agregado raíz del módulo competition.
Gestiona el ciclo de vida completo del torneo y su configuración.
"""

from datetime import datetime

from src.modules.golf_course.domain.value_objects.golf_course_id import GolfCourseId
from src.modules.user.domain.value_objects.user_id import UserId
from src.shared.domain.events.domain_event import DomainEvent
from src.shared.domain.value_objects.country_code import CountryCode

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
from ..value_objects.play_mode import PlayMode
from ..value_objects.team_assignment import TeamAssignment
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


class CompetitionStateError(Exception):
    """Excepción lanzada cuando se intenta una operación en un estado inválido."""

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
        team_1_name: str,
        team_2_name: str,
        play_mode: PlayMode,
        max_players: int = DEFAULT_MAX_PLAYERS,
        team_assignment: TeamAssignment = TeamAssignment.MANUAL,
        status: CompetitionStatus = CompetitionStatus.DRAFT,
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
        domain_events: list[DomainEvent] | None = None,
        max_playing_handicap: int | None = None,
        enrollment_opens_days_before: int | None = None,
        visibility: Visibility = Visibility.PRIVATE,
    ):
        # Validaciones de invariantes
        self._validate_team_names(team_1_name, team_2_name)
        self._validate_max_players(max_players)
        if max_playing_handicap is not None:
            self._validate_max_playing_handicap(max_playing_handicap)

        # Asignación de atributos privados (encapsulación)
        self._id = id
        self._creator_id = creator_id
        self._name = name
        self._dates = dates
        self._location = location
        self._team_1_name = team_1_name
        self._team_2_name = team_2_name
        self._play_mode = play_mode
        self._max_players = max_players
        self._team_assignment = team_assignment
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
        team_1_name: str,
        team_2_name: str,
        play_mode: PlayMode,
        max_players: int = DEFAULT_MAX_PLAYERS,
        team_assignment: TeamAssignment = TeamAssignment.MANUAL,
        max_playing_handicap: int | None = None,
        enrollment_opens_days_before: int | None = None,
        visibility: Visibility = Visibility.PRIVATE,
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
    def _validate_team_names(team_1_name: str, team_2_name: str) -> None:
        """Valida que los nombres de equipos sean válidos."""
        if not team_1_name or not team_1_name.strip():
            raise ValueError("El nombre del equipo 1 no puede estar vacío")

        if not team_2_name or not team_2_name.strip():
            raise ValueError("El nombre del equipo 2 no puede estar vacío")

        if team_1_name.strip().lower() == team_2_name.strip().lower():
            raise ValueError("Los nombres de los equipos deben ser diferentes")

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
    def team_1_name(self) -> str:
        return self._team_1_name

    @property
    def team_2_name(self) -> str:
        return self._team_2_name

    @property
    def play_mode(self) -> PlayMode:
        return self._play_mode

    @property
    def max_players(self) -> int:
        return self._max_players

    @property
    def team_assignment(self) -> TeamAssignment:
        return self._team_assignment

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

    def _update_team_names(self, team_1_name: str | None, team_2_name: str | None) -> None:
        """Cambia los nombres de los equipos, validandolos como pareja.

        Se validan juntos porque la regla es de los dos —no pueden llamarse
        igual—, asi que cambiar uno solo tambien hay que mirarlo contra el otro.
        """
        updated_team_1 = team_1_name if team_1_name is not None else self._team_1_name
        updated_team_2 = team_2_name if team_2_name is not None else self._team_2_name
        self._validate_team_names(updated_team_1, updated_team_2)

        if team_1_name is not None:
            self._team_1_name = team_1_name

        if team_2_name is not None:
            self._team_2_name = team_2_name

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

    def allows_deletion(self, has_schedule: bool) -> bool:
        """Verifica si el torneo todavía se puede borrar del todo (BE #333).

        Dos condiciones, y la segunda no se puede leer del estado. El estado
        tiene que permitirlo, y ademas **no puede haber calendario**: el estado
        se anda hacia atras —`revert-status` y `reopen-enrollments`— sin
        deshacer las rondas, asi que un torneo ya jugado puede volver a ACTIVE
        con sus golpes dentro. Mirando solo el estado, la cascada se los
        llevaria.

        El sorteo de equipos no entra (21 sep): se protege lo jugado, no lo
        preparado. Sin rondas no hay partidos ni golpes, y el sorteo se rehace.

        Args:
            has_schedule: Si ya tiene rondas. Solo se crean en CLOSED, asi que
                tenerlas significa que este torneo paso de ahi.
        """
        return self._status.allows_deletion() and not has_schedule

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
    ) -> None:
        """
        Actualiza la información del torneo, mientras las inscripciones estén abiertas.

        Raises:
            CompetitionStateError: Si no está en estado DRAFT
            ValueError: Si los nuevos valores no son válidos
        """
        if not self.allows_modifications():
            raise CompetitionStateError(
                f"No se puede modificar la configuración en estado {self._status.value}. "
                f"Solo mientras las inscripciones están abiertas."
            )

        if name is not None:
            self._name = name

        if dates is not None:
            # Mover las fechas ya no puede invalidar la apertura: son dias de
            # antelacion, asi que la apertura se mueve CON el torneo. Eso es lo
            # que se buscaba al dejar de guardar el instante (BE #332)
            self._dates = dates

        if location is not None:
            self._location = location

        if play_mode is not None:
            self._play_mode = play_mode

        if max_players is not None:
            self._validate_max_players(max_players)
            self._max_players = max_players

        if team_assignment is not None:
            self._team_assignment = team_assignment

        if max_playing_handicap is not None:
            self._validate_max_playing_handicap(max_playing_handicap)
            self._max_playing_handicap = max_playing_handicap

        if visibility is not None:
            self._visibility = visibility

        self._update_team_names(team_1_name, team_2_name)

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
        - Solo en estado DRAFT
        - El país del campo debe ser compatible con la location de la competición
        - No se permiten duplicados

        Raises:
            CompetitionStateError: Si las inscripciones ya no están abiertas
            ValueError: Si el país no es compatible o el campo ya existe
        """
        if not self.allows_modifications():
            raise CompetitionStateError(
                f"Solo puedes añadir campos de golf mientras las inscripciones "
                f"están abiertas. Estado actual: {self._status.value}"
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
        if country_code == self._location.main_country:
            return True

        if self._location.adjacent_country_1 and country_code == self._location.adjacent_country_1:
            return True

        return bool(
            self._location.adjacent_country_2 and country_code == self._location.adjacent_country_2
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
