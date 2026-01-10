"""
Enrollment Entity - Representa la inscripción de un jugador en una competición.

Esta entidad gestiona el estado de participación de un jugador en un torneo.
"""

from datetime import datetime
from decimal import Decimal

from src.modules.user.domain.value_objects.user_id import UserId
from src.shared.domain.events.domain_event import DomainEvent

from ..events.enrollment_approved_event import EnrollmentApprovedEvent
from ..events.enrollment_cancelled_event import EnrollmentCancelledEvent
from ..events.enrollment_requested_event import EnrollmentRequestedEvent
from ..events.enrollment_withdrawn_event import EnrollmentWithdrawnEvent
from ..value_objects.competition_id import CompetitionId
from ..value_objects.enrollment_id import EnrollmentId
from ..value_objects.enrollment_status import EnrollmentStatus


class EnrollmentStateError(Exception):
    """Excepción lanzada cuando se intenta una operación en un estado inválido."""

    pass


class Enrollment:
    """
    Entidad Enrollment - Representa una inscripción de jugador.

    Gestiona:
    - Estado de inscripción (solicitudes, invitaciones, aprobaciones)
    - Asignación a equipo
    - Hándicap personalizado (override del oficial)

    Invariantes:
    - competition_id y user_id no pueden ser None
    - custom_handicap debe estar en rango válido si se especifica
    - Las transiciones de estado deben ser válidas
    - team_id puede ser None hasta que se asigne

    Ejemplos:
        >>> enrollment = Enrollment.request(
        ...     id=EnrollmentId.generate(),
        ...     competition_id=CompetitionId.generate(),
        ...     user_id=UserId.generate()
        ... )
        >>> enrollment.status
        <EnrollmentStatus.REQUESTED: 'REQUESTED'>
        >>> enrollment.approve()
        >>> enrollment.status
        <EnrollmentStatus.APPROVED: 'APPROVED'>
    """

    def __init__(
        self,
        id: EnrollmentId,
        competition_id: CompetitionId,
        user_id: UserId,
        status: EnrollmentStatus,
        team_id: str | None = None,
        custom_handicap: Decimal | None = None,
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
        domain_events: list[DomainEvent] | None = None,
    ):
        """
        Constructor de Enrollment.

        Args:
            id: Identificador único de la inscripción
            competition_id: ID de la competición
            user_id: ID del jugador
            status: Estado de la inscripción
            team_id: ID del equipo asignado (opcional)
            custom_handicap: Hándicap personalizado (opcional, DECIMAL(4,1))
            created_at: Timestamp de creación
            updated_at: Timestamp de última actualización
            domain_events: Lista de eventos de dominio
        """
        # Validaciones
        if custom_handicap is not None:
            self._validate_custom_handicap(custom_handicap)

        # Asignación de atributos
        self.id = id
        self.competition_id = competition_id
        self.user_id = user_id
        self.status = status
        self.team_id = team_id
        self.custom_handicap = custom_handicap
        self.created_at = created_at or datetime.now()
        self.updated_at = updated_at or datetime.now()
        self._domain_events: list[DomainEvent] = domain_events or []

    @classmethod
    def request(
        cls, id: EnrollmentId, competition_id: CompetitionId, user_id: UserId
    ) -> "Enrollment":
        """
        Factory method para crear una solicitud de inscripción.

        El jugador solicita unirse (REQUESTED).

        Args:
            id: ID del enrollment
            competition_id: ID de la competición
            user_id: ID del jugador

        Returns:
            Enrollment: Nueva inscripción con evento emitido
        """
        enrollment = cls(
            id=id,
            competition_id=competition_id,
            user_id=user_id,
            status=EnrollmentStatus.REQUESTED,
        )

        # Emitir evento
        event = EnrollmentRequestedEvent(
            enrollment_id=str(enrollment.id),
            competition_id=str(enrollment.competition_id),
            user_id=str(enrollment.user_id),
        )
        enrollment._add_domain_event(event)

        return enrollment

    @classmethod
    def invite(
        cls, id: EnrollmentId, competition_id: CompetitionId, user_id: UserId
    ) -> "Enrollment":
        """
        Factory method para crear una invitación.

        El creador invita a un jugador (INVITED).

        Args:
            id: ID del enrollment
            competition_id: ID de la competición
            user_id: ID del jugador invitado

        Returns:
            Enrollment: Nueva invitación
        """
        enrollment = cls(
            id=id,
            competition_id=competition_id,
            user_id=user_id,
            status=EnrollmentStatus.INVITED,
        )

        # TODO: Emitir evento EnrollmentInvitedEvent (si se crea)

        return enrollment

    @classmethod
    def direct_enroll(
        cls,
        id: EnrollmentId,
        competition_id: CompetitionId,
        user_id: UserId,
        custom_handicap: Decimal | None = None,
    ) -> "Enrollment":
        """
        Factory method para inscripción directa por el creador.

        El creador inscribe directamente sin solicitud (APPROVED).

        Args:
            id: ID del enrollment
            competition_id: ID de la competición
            user_id: ID del jugador
            custom_handicap: Hándicap personalizado (opcional)

        Returns:
            Enrollment: Inscripción directamente aprobada con evento emitido
        """
        enrollment = cls(
            id=id,
            competition_id=competition_id,
            user_id=user_id,
            status=EnrollmentStatus.APPROVED,
            custom_handicap=custom_handicap,
        )

        # Emitir evento
        event = EnrollmentApprovedEvent(
            enrollment_id=str(enrollment.id),
            competition_id=str(enrollment.competition_id),
            user_id=str(enrollment.user_id),
        )
        enrollment._add_domain_event(event)

        return enrollment

    def _validate_custom_handicap(self, handicap: Decimal) -> None:
        """
        Valida que el hándicap personalizado esté en rango válido.

        Args:
            handicap: Valor del hándicap a validar

        Raises:
            ValueError: Si el hándicap no está en rango válido (-10.0 a 54.0)
        """
        min_handicap = Decimal("-10.0")
        max_handicap = Decimal("54.0")

        if handicap < min_handicap or handicap > max_handicap:
            raise ValueError(
                f"El hándicap personalizado debe estar entre {min_handicap} y {max_handicap}. "
                f"Se recibió: {handicap}"
            )

    # ===========================================
    # MÉTODOS DE CONSULTA (QUERIES)
    # ===========================================

    def is_pending(self) -> bool:
        """Verifica si está pendiente de acción (REQUESTED o INVITED)."""
        return self.status.is_pending()

    def is_approved(self) -> bool:
        """Verifica si está aprobado/inscrito."""
        return self.status.is_active()

    def is_rejected(self) -> bool:
        """Verifica si fue rechazado."""
        return self.status == EnrollmentStatus.REJECTED

    def is_withdrawn(self) -> bool:
        """Verifica si el jugador se retiró."""
        return self.status == EnrollmentStatus.WITHDRAWN

    def has_team_assigned(self) -> bool:
        """Verifica si tiene equipo asignado."""
        return self.team_id is not None

    def has_custom_handicap(self) -> bool:
        """Verifica si tiene hándicap personalizado."""
        return self.custom_handicap is not None

    # ===========================================
    # MÉTODOS DE COMANDO (CAMBIOS DE ESTADO)
    # ===========================================

    def approve(self) -> None:
        """
        Aprueba la inscripción.

        Puede ser:
        - Aprobar solicitud (REQUESTED → APPROVED)
        - Aceptar invitación (INVITED → APPROVED)

        Raises:
            EnrollmentStateError: Si la transición no es válida
        """
        if not self.status.can_transition_to(EnrollmentStatus.APPROVED):
            raise EnrollmentStateError(
                f"No se puede aprobar un enrollment en estado {self.status.value}"
            )

        self.status = EnrollmentStatus.APPROVED
        self.updated_at = datetime.now()

        # Emitir evento
        event = EnrollmentApprovedEvent(
            enrollment_id=str(self.id),
            competition_id=str(self.competition_id),
            user_id=str(self.user_id),
        )
        self._add_domain_event(event)

    def reject(self) -> None:
        """
        Rechaza la inscripción.

        Puede ser:
        - Rechazar solicitud (REQUESTED → REJECTED)
        - Declinar invitación (INVITED → REJECTED)

        Raises:
            EnrollmentStateError: Si la transición no es válida
        """
        if not self.status.can_transition_to(EnrollmentStatus.REJECTED):
            raise EnrollmentStateError(
                f"No se puede rechazar un enrollment en estado {self.status.value}"
            )

        self.status = EnrollmentStatus.REJECTED
        self.updated_at = datetime.now()

        # TODO: Emitir evento EnrollmentRejectedEvent (si se crea)

    def withdraw(self, reason: str | None = None) -> None:
        """
        Retira la inscripción voluntariamente.

        Solo desde APPROVED → WITHDRAWN.

        Args:
            reason: Razón del retiro (opcional)

        Raises:
            EnrollmentStateError: Si la transición no es válida
        """
        if not self.status.can_transition_to(EnrollmentStatus.WITHDRAWN):
            raise EnrollmentStateError(
                f"No se puede retirar un enrollment en estado {self.status.value}. "
                f"Solo se permite desde APPROVED."
            )

        self.status = EnrollmentStatus.WITHDRAWN
        self.updated_at = datetime.now()

        # Emitir evento
        event = EnrollmentWithdrawnEvent(
            enrollment_id=str(self.id),
            competition_id=str(self.competition_id),
            user_id=str(self.user_id),
            reason=reason,
        )
        self._add_domain_event(event)

    def cancel(self, reason: str | None = None) -> None:
        """
        Cancela la solicitud o declina la invitación.

        Solo desde REQUESTED o INVITED → CANCELLED.
        Diferencia con withdraw: cancel es antes de estar inscrito.

        Args:
            reason: Razón de la cancelación (opcional)

        Raises:
            EnrollmentStateError: Si la transición no es válida

        Ejemplos:
            >>> # Jugador cancela su solicitud
            >>> enrollment = Enrollment.request(id, comp_id, user_id)
            >>> enrollment.cancel("Cambié de planes")
            >>> enrollment.status
            <EnrollmentStatus.CANCELLED: 'CANCELLED'>

            >>> # Jugador declina invitación
            >>> enrollment2 = Enrollment.invite(id, comp_id, user_id)
            >>> enrollment2.cancel("No puedo asistir")
        """
        if not self.status.can_transition_to(EnrollmentStatus.CANCELLED):
            raise EnrollmentStateError(
                f"No se puede cancelar un enrollment en estado {self.status.value}. "
                f"Solo se permite desde REQUESTED o INVITED."
            )

        self.status = EnrollmentStatus.CANCELLED
        self.updated_at = datetime.now()

        # Emitir evento
        event = EnrollmentCancelledEvent(
            enrollment_id=str(self.id),
            competition_id=str(self.competition_id),
            user_id=str(self.user_id),
            reason=reason,
        )
        self._add_domain_event(event)

    # ===========================================
    # MÉTODOS DE ACTUALIZACIÓN
    # ===========================================

    def assign_to_team(self, team_id: str) -> None:
        """
        Asigna el jugador a un equipo.

        Solo permitido si está APPROVED.

        Args:
            team_id: ID del equipo (típicamente "1" o "2")

        Raises:
            EnrollmentStateError: Si no está aprobado
            ValueError: Si team_id está vacío
        """
        if not self.is_approved():
            raise EnrollmentStateError(
                f"Solo se pueden asignar equipos a enrollments aprobados. "
                f"Estado actual: {self.status.value}"
            )

        if not team_id or not team_id.strip():
            raise ValueError("El ID del equipo no puede estar vacío")

        self.team_id = team_id.strip()
        self.updated_at = datetime.now()

        # TODO: Emitir evento EnrollmentTeamAssignedEvent (si se crea)

    def set_custom_handicap(self, handicap: Decimal) -> None:
        """
        Establece un hándicap personalizado.

        El creador puede override el hándicap oficial del jugador.
        Útil para equilibrar equipos o situaciones especiales.

        Args:
            handicap: Hándicap personalizado (DECIMAL(4,1))

        Raises:
            ValueError: Si el hándicap no es válido
        """
        self._validate_custom_handicap(handicap)

        self.custom_handicap = handicap
        self.updated_at = datetime.now()

        # TODO: Emitir evento EnrollmentHandicapUpdatedEvent (si se crea)

    def remove_custom_handicap(self) -> None:
        """
        Elimina el hándicap personalizado.

        Se usará el hándicap oficial del User.
        """
        self.custom_handicap = None
        self.updated_at = datetime.now()

    # ===========================================
    # DOMAIN EVENTS
    # ===========================================

    def _add_domain_event(self, event: DomainEvent) -> None:
        """
        Añade un evento de dominio a la lista, inicializándola si es necesario.
        """
        if not hasattr(self, "_domain_events") or self._domain_events is None:
            self._domain_events: list[DomainEvent] = []
        self._domain_events.append(event)

    def get_domain_events(self) -> list[DomainEvent]:
        """Obtiene los eventos de dominio pendientes."""
        if not hasattr(self, "_domain_events") or self._domain_events is None:
            self._domain_events: list[DomainEvent] = []
        return self._domain_events.copy()

    def clear_domain_events(self) -> None:
        """Limpia los eventos de dominio después de procesarlos."""
        if hasattr(self, "_domain_events") and self._domain_events is not None:
            self._domain_events.clear()

    # ===========================================
    # MÉTODOS ESPECIALES
    # ===========================================

    def __str__(self) -> str:
        """Representación string legible."""
        return f"Enrollment({self.user_id} → Competition {self.competition_id}, {self.status.value})"

    def __eq__(self, other) -> bool:
        """Operador de igualdad - Comparación por identidad (ID)."""
        return isinstance(other, Enrollment) and self.id == other.id

    def __hash__(self) -> int:
        """Hash del objeto basado en el ID."""
        return hash(self.id)
