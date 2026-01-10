"""
Competition Entity - Representa una competición/torneo de golf formato Ryder Cup.

Esta es el agregado raíz del módulo competition.
Gestiona el ciclo de vida completo del torneo y su configuración.
"""

from datetime import datetime

from src.modules.user.domain.value_objects.user_id import UserId
from src.shared.domain.events.domain_event import DomainEvent

from ..events.competition_activated_event import CompetitionActivatedEvent
from ..events.competition_cancelled_event import CompetitionCancelledEvent
from ..events.competition_completed_event import CompetitionCompletedEvent
from ..events.competition_created_event import CompetitionCreatedEvent
from ..events.competition_enrollments_closed_event import (
    CompetitionEnrollmentsClosedEvent,
)
from ..events.competition_started_event import CompetitionStartedEvent
from ..events.competition_updated_event import CompetitionUpdatedEvent
from ..value_objects.competition_id import CompetitionId
from ..value_objects.competition_name import CompetitionName
from ..value_objects.competition_status import CompetitionStatus
from ..value_objects.date_range import DateRange
from ..value_objects.handicap_settings import HandicapSettings
from ..value_objects.location import Location
from ..value_objects.team_assignment import TeamAssignment

# Constantes de validación
MIN_PLAYERS = 2
MAX_PLAYERS = 100


class CompetitionStateError(Exception):
    """Excepción lanzada cuando se intenta una operación en un estado inválido."""

    pass


class Competition:
    """
    Entidad Competition - Representa un torneo de golf.

    Agregado raíz que gestiona:
    - Configuración del torneo (nombre, fechas, ubicación, hándicap)
    - Equipos (nombres de los dos equipos)
    - Ciclo de vida (estados: DRAFT, ACTIVE, CLOSED, IN_PROGRESS, COMPLETED, CANCELLED)
    - Inscripciones (mediante agregado Enrollment)

    Invariantes:
    - El creador no puede ser None
    - El nombre debe ser válido
    - Las fechas deben ser un rango válido
    - Los nombres de equipos no pueden estar vacíos
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
        ...     handicap_settings=HandicapSettings(HandicapType.PERCENTAGE, 90)
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
        handicap_settings: HandicapSettings,
        max_players: int = 24,
        team_assignment: TeamAssignment = TeamAssignment.MANUAL,
        status: CompetitionStatus = CompetitionStatus.DRAFT,
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
        domain_events: list[DomainEvent] | None = None,
    ):
        """
        Constructor de Competition.

        Args:
            id: Identificador único de la competición
            creator_id: ID del usuario que creó el torneo
            name: Nombre del torneo
            dates: Rango de fechas del torneo
            location: Ubicación geográfica
            team_1_name: Nombre del equipo 1
            team_2_name: Nombre del equipo 2
            handicap_settings: Configuración de hándicap
            status: Estado inicial (default: DRAFT)
            created_at: Timestamp de creación
            updated_at: Timestamp de última actualización
            domain_events: Lista de eventos de dominio
        """
        # Validaciones de invariantes
        self._validate_team_names(team_1_name, team_2_name)

        # Asignación de atributos
        self.id = id
        self.creator_id = creator_id
        self.name = name
        self.dates = dates
        self.location = location
        self.team_1_name = team_1_name
        self.team_2_name = team_2_name
        self.handicap_settings = handicap_settings
        self.max_players = max_players
        self.team_assignment = team_assignment
        self.status = status
        self.created_at = created_at or datetime.now()
        self.updated_at = updated_at or datetime.now()
        self._domain_events: list[DomainEvent] = domain_events or []

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
        handicap_settings: HandicapSettings,
        max_players: int = 24,
        team_assignment: TeamAssignment = TeamAssignment.MANUAL,
    ) -> "Competition":
        """
        Factory method para crear una nueva competición.

        Crea la competición y emite el evento CompetitionCreatedEvent.

        Args:
            (mismos que __init__)

        Returns:
            Competition: Nueva instancia con evento emitido
        """
        competition = cls(
            id=id,
            creator_id=creator_id,
            name=name,
            dates=dates,
            location=location,
            team_1_name=team_1_name,
            team_2_name=team_2_name,
            handicap_settings=handicap_settings,
            max_players=max_players,
            team_assignment=team_assignment,
            status=CompetitionStatus.DRAFT,
        )

        # Emitir evento de creación
        event = CompetitionCreatedEvent(
            competition_id=str(competition.id),
            creator_id=str(competition.creator_id),
            name=str(competition.name),
        )
        competition._add_domain_event(event)

        return competition

    def _validate_team_names(self, team_1_name: str, team_2_name: str) -> None:
        """
        Valida que los nombres de equipos sean válidos.

        Args:
            team_1_name: Nombre del equipo 1
            team_2_name: Nombre del equipo 2

        Raises:
            ValueError: Si algún nombre está vacío o los nombres son iguales
        """
        if not team_1_name or not team_1_name.strip():
            raise ValueError("El nombre del equipo 1 no puede estar vacío")

        if not team_2_name or not team_2_name.strip():
            raise ValueError("El nombre del equipo 2 no puede estar vacío")

        if team_1_name.strip().lower() == team_2_name.strip().lower():
            raise ValueError("Los nombres de los equipos deben ser diferentes")

    # ===========================================
    # MÉTODOS DE CONSULTA (QUERIES)
    # ===========================================

    def is_creator(self, user_id: UserId) -> bool:
        """
        Verifica si un usuario es el creador del torneo.

        Args:
            user_id: ID del usuario a verificar

        Returns:
            bool: True si es el creador
        """
        return self.creator_id == user_id

    def is_draft(self) -> bool:
        """Verifica si el torneo está en borrador."""
        return self.status == CompetitionStatus.DRAFT

    def is_active(self) -> bool:
        """Verifica si el torneo está activo (inscripciones abiertas)."""
        return self.status == CompetitionStatus.ACTIVE

    def is_in_progress(self) -> bool:
        """Verifica si el torneo está en curso."""
        return self.status == CompetitionStatus.IN_PROGRESS

    def is_completed(self) -> bool:
        """Verifica si el torneo ha finalizado."""
        return self.status == CompetitionStatus.COMPLETED

    def is_cancelled(self) -> bool:
        """Verifica si el torneo fue cancelado."""
        return self.status == CompetitionStatus.CANCELLED

    def allows_enrollments(self) -> bool:
        """
        Verifica si el torneo permite inscripciones.

        Returns:
            bool: True si está en estado ACTIVE
        """
        return self.status == CompetitionStatus.ACTIVE

    def allows_modifications(self) -> bool:
        """
        Verifica si el torneo permite modificar configuración.

        Returns:
            bool: True si está en estado DRAFT
        """
        return self.status == CompetitionStatus.DRAFT

    # ===========================================
    # MÉTODOS DE COMANDO (CAMBIOS DE ESTADO)
    # ===========================================

    def activate(self) -> None:
        """
        Activa el torneo (DRAFT → ACTIVE).

        Abre las inscripciones para jugadores.

        Raises:
            CompetitionStateError: Si la transición no es válida
        """
        if not self.status.can_transition_to(CompetitionStatus.ACTIVE):
            raise CompetitionStateError(
                f"No se puede activar una competición en estado {self.status.value}"
            )

        self.status = CompetitionStatus.ACTIVE
        self.updated_at = datetime.now()

        # Emitir evento
        event = CompetitionActivatedEvent(
            competition_id=str(self.id),
            name=str(self.name),
            start_date=self.dates.start_date.isoformat(),
        )
        self._add_domain_event(event)

    def close_enrollments(self, total_enrollments: int = 0) -> None:
        """
        Cierra las inscripciones (ACTIVE → CLOSED).

        Ya no se permiten nuevas inscripciones.

        Args:
            total_enrollments: Número total de inscripciones aprobadas

        Raises:
            CompetitionStateError: Si la transición no es válida
        """
        if not self.status.can_transition_to(CompetitionStatus.CLOSED):
            raise CompetitionStateError(
                f"No se pueden cerrar inscripciones en estado {self.status.value}"
            )

        self.status = CompetitionStatus.CLOSED
        self.updated_at = datetime.now()

        # Emitir evento
        event = CompetitionEnrollmentsClosedEvent(
            competition_id=str(self.id), total_enrollments=total_enrollments
        )
        self._add_domain_event(event)

    def start(self) -> None:
        """
        Inicia el torneo (CLOSED → IN_PROGRESS).

        El torneo comienza, los matches pueden jugarse.

        Raises:
            CompetitionStateError: Si la transición no es válida
        """
        if not self.status.can_transition_to(CompetitionStatus.IN_PROGRESS):
            raise CompetitionStateError(
                f"No se puede iniciar una competición en estado {self.status.value}"
            )

        self.status = CompetitionStatus.IN_PROGRESS
        self.updated_at = datetime.now()

        # Emitir evento
        event = CompetitionStartedEvent(
            competition_id=str(self.id), name=str(self.name)
        )
        self._add_domain_event(event)

    def complete(self) -> None:
        """
        Finaliza el torneo (IN_PROGRESS → COMPLETED).

        El torneo ha terminado.

        Raises:
            CompetitionStateError: Si la transición no es válida
        """
        if not self.status.can_transition_to(CompetitionStatus.COMPLETED):
            raise CompetitionStateError(
                f"No se puede completar una competición en estado {self.status.value}"
            )

        self.status = CompetitionStatus.COMPLETED
        self.updated_at = datetime.now()

        # Emitir evento
        event = CompetitionCompletedEvent(
            competition_id=str(self.id), name=str(self.name)
        )
        self._add_domain_event(event)

    def cancel(self, reason: str | None = None) -> None:
        """
        Cancela el torneo (cualquier estado → CANCELLED).

        Args:
            reason: Razón opcional de la cancelación

        Raises:
            CompetitionStateError: Si ya está en estado final
        """
        if self.status.is_final():
            raise CompetitionStateError(
                f"No se puede cancelar una competición en estado final {self.status.value}"
            )

        if not self.status.can_transition_to(CompetitionStatus.CANCELLED):
            raise CompetitionStateError(
                f"No se puede cancelar desde estado {self.status.value}"
            )

        self.status = CompetitionStatus.CANCELLED
        self.updated_at = datetime.now()

        # Emitir evento
        event = CompetitionCancelledEvent(
            competition_id=str(self.id), name=str(self.name), reason=reason
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
        handicap_settings: HandicapSettings | None = None,
        max_players: int | None = None,
        team_assignment: TeamAssignment | None = None,
    ) -> None:
        """
        Actualiza la información del torneo.

        Solo permitido en estado DRAFT.

        Args:
            name: Nuevo nombre (opcional)
            dates: Nuevas fechas (opcional)
            location: Nueva ubicación (opcional)
            team_1_name: Nuevo nombre equipo 1 (opcional)
            team_2_name: Nuevo nombre equipo 2 (opcional)
            handicap_settings: Nueva configuración hándicap (opcional)
            max_players: Nuevo máximo de jugadores (opcional)
            team_assignment: Nueva asignación de equipos (opcional)

        Raises:
            CompetitionStateError: Si no está en estado DRAFT
            ValueError: Si los nuevos valores no son válidos
        """
        if not self.allows_modifications():
            raise CompetitionStateError(
                f"No se puede modificar la configuración en estado {self.status.value}. "
                f"Solo se permite en estado DRAFT."
            )

        # Actualizar campos si se proporcionan
        if name is not None:
            self.name = name

        if dates is not None:
            self.dates = dates

        if location is not None:
            self.location = location

        if handicap_settings is not None:
            self.handicap_settings = handicap_settings

        if max_players is not None:
            if not MIN_PLAYERS <= max_players <= MAX_PLAYERS:
                raise ValueError(
                    f"max_players debe estar entre {MIN_PLAYERS} y {MAX_PLAYERS}"
                )
            self.max_players = max_players

        if team_assignment is not None:
            self.team_assignment = team_assignment

        # Validar y actualizar nombres de equipos
        updated_team_1 = team_1_name if team_1_name is not None else self.team_1_name
        updated_team_2 = team_2_name if team_2_name is not None else self.team_2_name
        self._validate_team_names(updated_team_1, updated_team_2)

        if team_1_name is not None:
            self.team_1_name = team_1_name

        if team_2_name is not None:
            self.team_2_name = team_2_name

        self.updated_at = datetime.now()

        # Emitir evento
        event = CompetitionUpdatedEvent(
            competition_id=str(self.id), name=str(self.name)
        )
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
    # MÉTODOS ESPECIALES
    # ===========================================

    def __str__(self) -> str:
        """Representación string legible."""
        return f"{self.name} ({self.status.value})"

    def __eq__(self, other) -> bool:
        """Operador de igualdad - Comparación por identidad (ID)."""
        return isinstance(other, Competition) and self.id == other.id

    def __hash__(self) -> int:
        """Hash del objeto basado en el ID."""
        return hash(self.id)
