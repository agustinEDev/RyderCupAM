"""
Invitation Entity - Representa una invitacion a participar en una competicion.

Esta entidad gestiona el ciclo de vida de invitaciones enviadas por el creador.
"""

from datetime import datetime, timedelta

from src.modules.user.domain.value_objects.user_id import UserId

from ..exceptions.competition_violations import (
    InvalidInvitationStatusViolation,
    InvitationExpiredViolation,
    InvitationOnHoldViolation,
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
        sent_by_email: bool = False,
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
        # Si el organizador la mandó tecleando un correo (y no eligiendo a un usuario):
        # decide qué ve de ella (auditoría de la fase 6, B-01/B-03)
        self._sent_by_email = sent_by_email

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
        sent_by_email: bool = False,
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
            sent_by_email=sent_by_email,
        )

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
        sent_by_email: bool = False,
    ) -> "Invitation":
        """Reconstruye una invitacion desde la base de datos."""
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
            sent_by_email=sent_by_email,
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
    def sent_by_email(self) -> bool:
        """Si se mandó tecleando un correo (True) o eligiendo a un usuario (False)."""
        return self._sent_by_email

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

    def is_on_hold(self) -> bool:
        """Si espera a que se reabra la inscripcion (P1, 15 nov 2026)."""
        return self._status.is_on_hold()

    def is_open(self) -> bool:
        """Si sigue viva: pendiente o en espera."""
        return self._status.is_open()

    def is_for_user(self, user_id: UserId) -> bool:
        """Verifica si la invitacion es para el usuario dado (por user_id)."""
        return self._invitee_user_id is not None and self._invitee_user_id == user_id

    def is_for_email(self, email: str) -> bool:
        """Verifica si la invitacion es para el email dado."""
        return self._invitee_email == email.strip().lower()

    # ===========================================
    # METODOS DE COMANDO (CAMBIOS DE ESTADO)
    # ===========================================

    def _ata_a(self, quien: UserId | None) -> None:
        """Una enviada a un correo sin cuenta verificada queda atada a quien la responde
        (B-03: el organizador ve entonces su nombre, el de quien respondió)."""
        if self._invitee_user_id is None and quien is not None:
            self._invitee_user_id = quien

    def accept(self, respondida_por: UserId | None = None) -> None:
        """Acepta la invitacion (PENDING -> ACCEPTED). Sin invitado atado, la ata a quien
        la responde."""
        # En espera no se acepta: hay que esperar a que se reabra (P1). Esperando
        # no caduca, así que esto va antes que la caducidad
        if self.is_on_hold():
            raise InvitationOnHoldViolation()

        if self.is_expired():
            self._transition_to_expired()
            raise InvitationExpiredViolation("Cannot accept an expired invitation.")

        if not self._status.can_transition_to(InvitationStatus.ACCEPTED):
            raise InvalidInvitationStatusViolation(
                f"Cannot accept invitation in status {self._status.value}."
            )

        self._ata_a(respondida_por)
        now = datetime.now()
        self._status = InvitationStatus.ACCEPTED
        self._responded_at = now
        self._updated_at = now

    def decline(self, respondida_por: UserId | None = None) -> None:
        """Rechaza la invitacion (PENDING -> DECLINED). Como `accept`, la ata a quien
        responde si no lo estaba. Una en espera no caduca: se rechaza siempre."""
        if not self.is_on_hold() and self.is_expired():
            self._transition_to_expired()
            raise InvitationExpiredViolation("Cannot decline an expired invitation.")

        if not self._status.can_transition_to(InvitationStatus.DECLINED):
            raise InvalidInvitationStatusViolation(
                f"Cannot decline invitation in status {self._status.value}."
            )

        self._ata_a(respondida_por)
        now = datetime.now()
        self._status = InvitationStatus.DECLINED
        self._responded_at = now
        self._updated_at = now

    def reject_for_no_room(self) -> None:
        """Rechaza la invitacion por falta de plazas (PENDING u ON_HOLD -> NO_ROOM, #710).

        La rechaza la aplicacion, no el invitado: al ocuparse la ultima plaza (BE
        #359) o, si esperaba, al empezar o cancelarse la competicion (P3).
        """
        if not self._status.can_transition_to(InvitationStatus.NO_ROOM):
            raise InvalidInvitationStatusViolation(
                f"Cannot reject for no room an invitation in status {self._status.value}."
            )
        now = datetime.now()
        self._status = InvitationStatus.NO_ROOM
        self._responded_at = now
        self._updated_at = now

    def put_on_hold(self) -> None:
        """Se cierra la inscripcion: espera a que se reabra (PENDING -> ON_HOLD, P1).

        No se pierde, como pasaba con NO_ROOM hasta el 15 nov 2026: si el
        organizador reabre, vuelve a PENDING (`resume`).
        """
        if not self._status.can_transition_to(InvitationStatus.ON_HOLD):
            raise InvalidInvitationStatusViolation(
                f"Cannot put on hold an invitation in status {self._status.value}."
            )
        self._status = InvitationStatus.ON_HOLD
        self._updated_at = datetime.now()

    def resume(self) -> None:
        """Se reabre la inscripcion: se puede aceptar otra vez (ON_HOLD -> PENDING, P2).

        Con 7 días nuevos para responder: esperando no caducaba (Agustín, 15 nov 2026).
        """
        if not self.is_on_hold():
            raise InvalidInvitationStatusViolation(
                f"Cannot resume an invitation in status {self._status.value}."
            )
        now = datetime.now()
        self._status = InvitationStatus.PENDING
        self._expires_at = now + timedelta(days=INVITATION_EXPIRATION_DAYS)
        self._updated_at = now

    def cancel(self) -> None:
        """La retira quien invita (PENDING u ON_HOLD -> CANCELLED, BE #359).

        Sin aviso al invitado: en sus invitaciones pasa a cancelada y ya no se
        puede aceptar.
        """
        if not self._status.can_transition_to(InvitationStatus.CANCELLED):
            raise InvalidInvitationStatusViolation(
                f"Cannot cancel an invitation in status {self._status.value}."
            )
        now = datetime.now()
        self._status = InvitationStatus.CANCELLED
        self._responded_at = now
        self._updated_at = now

    def check_expiration(self) -> None:
        """Verifica y actualiza el estado si la invitacion ha expirado; en espera no caduca."""
        if self.is_expired():
            self._transition_to_expired()

    def _transition_to_expired(self) -> None:
        """Transiciona internamente a EXPIRED: solo una pendiente; en espera no caduca."""
        if self.is_pending():
            self._status = InvitationStatus.EXPIRED
            self._updated_at = datetime.now()

    # ===========================================
    # METODOS ESPECIALES
    # ===========================================

    def __str__(self) -> str:
        return (
            f"Invitation({self._invitee_email} -> Competition {self._competition_id}, "
            f"{self._status.value})"
        )

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Invitation) and self._id == other._id

    def __hash__(self) -> int:
        return hash(self._id)
