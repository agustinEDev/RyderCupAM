"""
Invitation Entity - Representa una invitacion a participar en una competicion.

Esta entidad gestiona el ciclo de vida de invitaciones enviadas por el creador.
"""

from datetime import datetime, timedelta

from src.modules.user.domain.value_objects.user_id import UserId
from src.shared.domain.events.domain_event import DomainEvent

from ..events.invitation_accepted_event import InvitationAcceptedEvent
from ..events.invitation_created_event import InvitationCreatedEvent
from ..events.invitation_declined_event import InvitationDeclinedEvent
from ..exceptions.competition_violations import (
    InvalidInvitationStatusViolation,
    InvitationExpiredViolation,
)
from ..value_objects.competition_id import CompetitionId
from ..value_objects.invitation_id import InvitationId
from ..value_objects.invitation_status import InvitationStatus

INVITATION_EXPIRATION_DAYS = 7
MAX_PERSONAL_MESSAGE_LENGTH = 500


class Invitation:
    """
    Entidad Invitation - Representa una invitacion a una competicion.

    Gestiona:
    - Envio de invitaciones por email o user_id
    - Respuesta (aceptar/rechazar)
    - Expiracion automatica (7 dias)

    Invariantes:
    - competition_id e inviter_id no pueden ser None
    - invitee_email no puede ser None ni vacio
    - expires_at debe ser futuro respecto a created_at
    - Solo PENDING permite transiciones
    """

    def __init__(
        self,
        id: InvitationId,
        competition_id: CompetitionId,
        inviter_id: UserId,
        invitee_email: str,
        status: InvitationStatus,
        expires_at: datetime,
        invitee_user_id: UserId | None = None,
        personal_message: str | None = None,
        responded_at: datetime | None = None,
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
        domain_events: list[DomainEvent] | None = None,
    ):
        if not invitee_email or not invitee_email.strip():
            raise ValueError("invitee_email no puede estar vacio")

        if personal_message and len(personal_message) > MAX_PERSONAL_MESSAGE_LENGTH:
            raise ValueError("personal_message no puede exceder 500 caracteres")

        self._id = id
        self._competition_id = competition_id
        self._inviter_id = inviter_id
        self._invitee_email = invitee_email.strip().lower()
        self._invitee_user_id = invitee_user_id
        self._status = status
        self._personal_message = personal_message
        self._expires_at = expires_at
        self._responded_at = responded_at
        self._created_at = created_at or datetime.now()
        self._updated_at = updated_at or datetime.now()
        self._domain_events: list[DomainEvent] = domain_events or []

    # ===========================================
    # FACTORY METHODS
    # ===========================================

    @classmethod
    def create(
        cls,
        id: InvitationId,
        competition_id: CompetitionId,
        inviter_id: UserId,
        invitee_email: str,
        invitee_user_id: UserId | None = None,
        personal_message: str | None = None,
    ) -> "Invitation":
        """Factory method para crear una nueva invitacion con status PENDING."""
        now = datetime.now()
        invitation = cls(
            id=id,
            competition_id=competition_id,
            inviter_id=inviter_id,
            invitee_email=invitee_email,
            invitee_user_id=invitee_user_id,
            status=InvitationStatus.PENDING,
            personal_message=personal_message,
            expires_at=now + timedelta(days=INVITATION_EXPIRATION_DAYS),
            created_at=now,
            updated_at=now,
        )

        event = InvitationCreatedEvent(
            invitation_id=str(invitation._id),
            competition_id=str(invitation._competition_id),
            inviter_id=str(invitation._inviter_id),
            invitee_email=invitation._invitee_email,
        )
        invitation.add_domain_event(event)

        return invitation

    @classmethod
    def reconstruct(
        cls,
        id: InvitationId,
        competition_id: CompetitionId,
        inviter_id: UserId,
        invitee_email: str,
        status: InvitationStatus,
        expires_at: datetime,
        invitee_user_id: UserId | None = None,
        personal_message: str | None = None,
        responded_at: datetime | None = None,
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
    ) -> "Invitation":
        """Reconstruye una invitacion desde la base de datos (sin domain events)."""
        return cls(
            id=id,
            competition_id=competition_id,
            inviter_id=inviter_id,
            invitee_email=invitee_email,
            invitee_user_id=invitee_user_id,
            status=status,
            personal_message=personal_message,
            expires_at=expires_at,
            responded_at=responded_at,
            created_at=created_at,
            updated_at=updated_at,
        )

    # ===========================================
    # PROPERTIES (Encapsulacion — solo lectura)
    # ===========================================

    @property
    def id(self) -> InvitationId:
        return self._id

    @property
    def competition_id(self) -> CompetitionId:
        return self._competition_id

    @property
    def inviter_id(self) -> UserId:
        return self._inviter_id

    @property
    def invitee_email(self) -> str:
        return self._invitee_email

    @property
    def invitee_user_id(self) -> UserId | None:
        return self._invitee_user_id

    @property
    def status(self) -> InvitationStatus:
        return self._status

    @property
    def personal_message(self) -> str | None:
        return self._personal_message

    @property
    def expires_at(self) -> datetime:
        return self._expires_at

    @property
    def responded_at(self) -> datetime | None:
        return self._responded_at

    @property
    def created_at(self) -> datetime:
        return self._created_at

    @property
    def updated_at(self) -> datetime:
        return self._updated_at

    # ===========================================
    # METODOS DE CONSULTA (QUERIES)
    # ===========================================

    def is_expired(self) -> bool:
        """Verifica si la invitacion ha expirado."""
        return datetime.now() >= self._expires_at

    def is_pending(self) -> bool:
        """Verifica si la invitacion esta pendiente."""
        return self._status.is_pending()

    def is_for_user(self, user_id: UserId) -> bool:
        """Verifica si la invitacion es para el usuario dado (por user_id)."""
        return self._invitee_user_id is not None and self._invitee_user_id == user_id

    def is_for_email(self, email: str) -> bool:
        """Verifica si la invitacion es para el email dado."""
        return self._invitee_email == email.strip().lower()

    # ===========================================
    # METODOS DE COMANDO (CAMBIOS DE ESTADO)
    # ===========================================

    def accept(self) -> None:
        """Acepta la invitacion (PENDING -> ACCEPTED)."""
        if self.is_expired():
            self._transition_to_expired()
            raise InvitationExpiredViolation("Cannot accept an expired invitation.")

        if not self._status.can_transition_to(InvitationStatus.ACCEPTED):
            raise InvalidInvitationStatusViolation(
                f"Cannot accept invitation in status {self._status.value}."
            )

        now = datetime.now()
        self._status = InvitationStatus.ACCEPTED
        self._responded_at = now
        self._updated_at = now

        event = InvitationAcceptedEvent(
            invitation_id=str(self._id),
            competition_id=str(self._competition_id),
            invitee_user_id=str(self._invitee_user_id) if self._invitee_user_id is not None else None,
        )
        self.add_domain_event(event)

    def decline(self) -> None:
        """Rechaza la invitacion (PENDING -> DECLINED)."""
        if self.is_expired():
            self._transition_to_expired()
            raise InvitationExpiredViolation("Cannot decline an expired invitation.")

        if not self._status.can_transition_to(InvitationStatus.DECLINED):
            raise InvalidInvitationStatusViolation(
                f"Cannot decline invitation in status {self._status.value}."
            )

        now = datetime.now()
        self._status = InvitationStatus.DECLINED
        self._responded_at = now
        self._updated_at = now

        event = InvitationDeclinedEvent(
            invitation_id=str(self._id),
            competition_id=str(self._competition_id),
            invitee_user_id=str(self._invitee_user_id) if self._invitee_user_id is not None else None,
        )
        self.add_domain_event(event)

    def check_expiration(self) -> None:
        """Verifica y actualiza el estado si la invitacion ha expirado."""
        if self._status == InvitationStatus.PENDING and self.is_expired():
            self._transition_to_expired()

    def _transition_to_expired(self) -> None:
        """Transiciona internamente a EXPIRED."""
        if self._status == InvitationStatus.PENDING:
            self._status = InvitationStatus.EXPIRED
            self._updated_at = datetime.now()

    # ===========================================
    # DOMAIN EVENTS
    # ===========================================

    def add_domain_event(self, event: DomainEvent) -> None:
        """Registra un evento de dominio en la entidad."""
        self._domain_events.append(event)

    def get_domain_events(self) -> list[DomainEvent]:
        return self._domain_events.copy()

    def clear_domain_events(self) -> None:
        self._domain_events.clear()

    # ===========================================
    # METODOS ESPECIALES
    # ===========================================

    def __str__(self) -> str:
        return (
            f"Invitation({self._invitee_email} -> Competition {self._competition_id}, "
            f"{self._status.value})"
        )

    def __eq__(self, other) -> bool:
        return isinstance(other, Invitation) and self._id == other._id

    def __hash__(self) -> int:
        return hash(self._id)
