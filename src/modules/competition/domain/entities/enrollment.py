"""
Enrollment Entity - Representa la inscripción de un jugador en una competición.

Esta entidad gestiona el estado de participación de un jugador en un torneo.
"""

from datetime import datetime
from decimal import Decimal

from src.modules.golf_course.domain.value_objects.tee_category import TeeCategory
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
    """

    def __init__(
        self,
        id: EnrollmentId,
        competition_id: CompetitionId,
        user_id: UserId,
        status: EnrollmentStatus,
        team_id: str | None = None,
        custom_handicap: Decimal | None = None,
        tee_category: TeeCategory | None = None,
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
        domain_events: list[DomainEvent] | None = None,
    ):
        # Validaciones
        if custom_handicap is not None:
            self._validate_custom_handicap(custom_handicap)

        # Asignación de atributos privados (encapsulación)
        self._id = id
        self._competition_id = competition_id
        self._user_id = user_id
        self._status = status
        self._team_id = team_id
        self._custom_handicap = custom_handicap
        self._tee_category = tee_category
        self._created_at = created_at or datetime.now()
        self._updated_at = updated_at or datetime.now()
        self._domain_events: list[DomainEvent] = domain_events or []

    @classmethod
    def request(
        cls,
        id: EnrollmentId,
        competition_id: CompetitionId,
        user_id: UserId,
        tee_category: TeeCategory | None = None,
    ) -> "Enrollment":
        """Factory method para crear una solicitud de inscripción."""
        enrollment = cls(
            id=id,
            competition_id=competition_id,
            user_id=user_id,
            status=EnrollmentStatus.REQUESTED,
            tee_category=tee_category,
        )

        event = EnrollmentRequestedEvent(
            enrollment_id=str(enrollment._id),
            competition_id=str(enrollment._competition_id),
            user_id=str(enrollment._user_id),
        )
        enrollment._add_domain_event(event)

        return enrollment

    @classmethod
    def invite(
        cls, id: EnrollmentId, competition_id: CompetitionId, user_id: UserId
    ) -> "Enrollment":
        """Factory method para crear una invitación."""
        return cls(
            id=id,
            competition_id=competition_id,
            user_id=user_id,
            status=EnrollmentStatus.INVITED,
        )

    @classmethod
    def direct_enroll(
        cls,
        id: EnrollmentId,
        competition_id: CompetitionId,
        user_id: UserId,
        custom_handicap: Decimal | None = None,
        tee_category: TeeCategory | None = None,
    ) -> "Enrollment":
        """Factory method para inscripción directa por el creador."""
        enrollment = cls(
            id=id,
            competition_id=competition_id,
            user_id=user_id,
            status=EnrollmentStatus.APPROVED,
            custom_handicap=custom_handicap,
            tee_category=tee_category,
        )

        event = EnrollmentApprovedEvent(
            enrollment_id=str(enrollment._id),
            competition_id=str(enrollment._competition_id),
            user_id=str(enrollment._user_id),
        )
        enrollment._add_domain_event(event)

        return enrollment

    @staticmethod
    def _validate_custom_handicap(handicap: Decimal) -> None:
        """Valida que el hándicap personalizado esté en rango válido."""
        min_handicap = Decimal("-10.0")
        max_handicap = Decimal("54.0")

        if handicap < min_handicap or handicap > max_handicap:
            raise ValueError(
                f"El hándicap personalizado debe estar entre {min_handicap} y {max_handicap}. "
                f"Se recibió: {handicap}"
            )

    # ===========================================
    # PROPERTIES (Encapsulación — solo lectura)
    # ===========================================

    @property
    def id(self) -> EnrollmentId:
        return self._id

    @property
    def competition_id(self) -> CompetitionId:
        return self._competition_id

    @property
    def user_id(self) -> UserId:
        return self._user_id

    @property
    def status(self) -> EnrollmentStatus:
        return self._status

    @property
    def team_id(self) -> str | None:
        return self._team_id

    @property
    def custom_handicap(self) -> Decimal | None:
        return self._custom_handicap

    @property
    def tee_category(self) -> TeeCategory | None:
        return self._tee_category

    @property
    def created_at(self) -> datetime:
        return self._created_at

    @property
    def updated_at(self) -> datetime:
        return self._updated_at

    # ===========================================
    # MÉTODOS DE CONSULTA (QUERIES)
    # ===========================================

    def is_pending(self) -> bool:
        """Verifica si está pendiente de acción (REQUESTED o INVITED)."""
        return self._status.is_pending()

    def is_approved(self) -> bool:
        """Verifica si está aprobado/inscrito."""
        return self._status.is_active()

    def is_rejected(self) -> bool:
        """Verifica si fue rechazado."""
        return self._status == EnrollmentStatus.REJECTED

    def is_withdrawn(self) -> bool:
        """Verifica si el jugador se retiró."""
        return self._status == EnrollmentStatus.WITHDRAWN

    def has_team_assigned(self) -> bool:
        """Verifica si tiene equipo asignado."""
        return self._team_id is not None

    def has_custom_handicap(self) -> bool:
        """Verifica si tiene hándicap personalizado."""
        return self._custom_handicap is not None

    # ===========================================
    # MÉTODOS DE COMANDO (CAMBIOS DE ESTADO)
    # ===========================================

    def approve(self) -> None:
        """Aprueba la inscripción (REQUESTED/INVITED → APPROVED)."""
        if not self._status.can_transition_to(EnrollmentStatus.APPROVED):
            raise EnrollmentStateError(
                f"No se puede aprobar un enrollment en estado {self._status.value}"
            )

        self._status = EnrollmentStatus.APPROVED
        self._updated_at = datetime.now()

        event = EnrollmentApprovedEvent(
            enrollment_id=str(self._id),
            competition_id=str(self._competition_id),
            user_id=str(self._user_id),
        )
        self._add_domain_event(event)

    def reject(self) -> None:
        """Rechaza la inscripción (REQUESTED/INVITED → REJECTED)."""
        if not self._status.can_transition_to(EnrollmentStatus.REJECTED):
            raise EnrollmentStateError(
                f"No se puede rechazar un enrollment en estado {self._status.value}"
            )

        self._status = EnrollmentStatus.REJECTED
        self._updated_at = datetime.now()

    def withdraw(self, reason: str | None = None) -> None:
        """Retira la inscripción voluntariamente (APPROVED → WITHDRAWN)."""
        if not self._status.can_transition_to(EnrollmentStatus.WITHDRAWN):
            raise EnrollmentStateError(
                f"No se puede retirar un enrollment en estado {self._status.value}. "
                f"Solo se permite desde APPROVED."
            )

        self._status = EnrollmentStatus.WITHDRAWN
        self._updated_at = datetime.now()

        event = EnrollmentWithdrawnEvent(
            enrollment_id=str(self._id),
            competition_id=str(self._competition_id),
            user_id=str(self._user_id),
            reason=reason,
        )
        self._add_domain_event(event)

    def cancel(self, reason: str | None = None) -> None:
        """Cancela la solicitud (REQUESTED/INVITED → CANCELLED)."""
        if not self._status.can_transition_to(EnrollmentStatus.CANCELLED):
            raise EnrollmentStateError(
                f"No se puede cancelar un enrollment en estado {self._status.value}. "
                f"Solo se permite desde REQUESTED o INVITED."
            )

        self._status = EnrollmentStatus.CANCELLED
        self._updated_at = datetime.now()

        event = EnrollmentCancelledEvent(
            enrollment_id=str(self._id),
            competition_id=str(self._competition_id),
            user_id=str(self._user_id),
            reason=reason,
        )
        self._add_domain_event(event)

    # ===========================================
    # MÉTODOS DE ACTUALIZACIÓN
    # ===========================================

    def assign_to_team(self, team_id: str) -> None:
        """Asigna el jugador a un equipo. Solo si APPROVED."""
        if not self.is_approved():
            raise EnrollmentStateError(
                f"Solo se pueden asignar equipos a enrollments aprobados. "
                f"Estado actual: {self._status.value}"
            )

        if not team_id or not team_id.strip():
            raise ValueError("El ID del equipo no puede estar vacío")

        self._team_id = team_id.strip()
        self._updated_at = datetime.now()

    def set_custom_handicap(self, handicap: Decimal) -> None:
        """Establece un hándicap personalizado."""
        self._validate_custom_handicap(handicap)
        self._custom_handicap = handicap
        self._updated_at = datetime.now()

    def remove_custom_handicap(self) -> None:
        """Elimina el hándicap personalizado."""
        self._custom_handicap = None
        self._updated_at = datetime.now()

    def set_tee_category(self, tee_category: TeeCategory) -> None:
        """Establece o cambia la categoría de tee del jugador."""
        self._tee_category = tee_category
        self._updated_at = datetime.now()

    def has_tee_assigned(self) -> bool:
        """Verifica si tiene tee asignado."""
        return self._tee_category is not None

    # ===========================================
    # DOMAIN EVENTS
    # ===========================================

    def _add_domain_event(self, event: DomainEvent) -> None:
        """Añade un evento de dominio a la lista, inicializándola si es necesario."""
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
        return (
            f"Enrollment({self._user_id} → Competition {self._competition_id}, "
            f"{self._status.value})"
        )

    def __eq__(self, other) -> bool:
        return isinstance(other, Enrollment) and self._id == other._id

    def __hash__(self) -> int:
        return hash(self._id)
