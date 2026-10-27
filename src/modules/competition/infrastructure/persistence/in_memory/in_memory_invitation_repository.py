"""In-Memory Invitation Repository para testing."""

from datetime import datetime

from src.modules.competition.domain.entities.invitation import Invitation
from src.modules.competition.domain.repositories.invitation_repository_interface import (
    InvitationRepositoryInterface,
)
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.invitacion_pendiente import (
    InvitacionPendiente,
)
from src.modules.competition.domain.value_objects.invitation_id import InvitationId
from src.modules.competition.domain.value_objects.invitation_status import InvitationStatus
from src.modules.user.domain.value_objects.user_id import UserId


def _suya_y_aceptable(inv: Invitation, user_id: UserId, email: str | None, now: datetime) -> bool:
    """PENDING y sin caducar en `now`, a su usuario o a su correo (sin mayúsculas ni espacios)."""
    correo = email.strip().lower() if email and email.strip() else None
    return (
        inv.status == InvitationStatus.PENDING
        and now < inv.expires_at
        and (inv.invitee_user_id == user_id or bool(correo and inv.invitee_email == correo))
    )


class InMemoryInvitationRepository(InvitationRepositoryInterface):
    """Implementacion en memoria del repositorio de invitaciones para testing."""

    def __init__(self):
        self._invitations: dict[InvitationId, Invitation] = {}

    async def add(self, invitation: Invitation) -> None:
        self._invitations[invitation.id] = invitation

    async def update(self, invitation: Invitation) -> None:
        if invitation.id in self._invitations:
            self._invitations[invitation.id] = invitation

    async def find_by_id(self, invitation_id: InvitationId) -> Invitation | None:
        return self._invitations.get(invitation_id)

    async def find_by_id_for_update(self, invitation_id: InvitationId) -> Invitation | None:
        # En memoria no hay transacciones que bloquear
        return self._invitations.get(invitation_id)

    async def find_by_competition(
        self,
        competition_id: CompetitionId,
        status: InvitationStatus | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> list[Invitation]:
        results = [
            inv
            for inv in self._invitations.values()
            if inv.competition_id == competition_id and (status is None or inv.status == status)
        ]
        # Sort by created_at desc
        results.sort(key=lambda x: x.created_at, reverse=True)
        return results[offset : offset + limit]

    async def find_by_invitee_email(
        self,
        email: str,
        status: InvitationStatus | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> list[Invitation]:
        normalized_email = email.strip().lower()
        results = [
            inv
            for inv in self._invitations.values()
            if inv.invitee_email == normalized_email and (status is None or inv.status == status)
        ]
        results.sort(key=lambda x: x.created_at, reverse=True)
        return results[offset : offset + limit]

    async def find_by_invitee_user_id(
        self,
        user_id: UserId,
        status: InvitationStatus | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> list[Invitation]:
        results = [
            inv
            for inv in self._invitations.values()
            if inv.invitee_user_id == user_id and (status is None or inv.status == status)
        ]
        results.sort(key=lambda x: x.created_at, reverse=True)
        return results[offset : offset + limit]

    async def find_acceptable_ids(
        self, invitation_ids: list[InvitationId], now: datetime
    ) -> set[InvitationId]:
        return {
            i
            for i in invitation_ids
            if (inv := self._invitations.get(i)) is not None
            and inv.status == InvitationStatus.PENDING
            and now < inv.expires_at
        }

    async def competiciones_con_invitacion_pendiente(
        self, user_id: UserId, email: str | None, now: datetime
    ) -> set[CompetitionId]:
        return {
            inv.competition_id
            for inv in self._invitations.values()
            if _suya_y_aceptable(inv, user_id, email, now)
        }

    async def pendiente_de(
        self, user_id: UserId, email: str | None, competition_id: CompetitionId, now: datetime
    ) -> InvitacionPendiente | None:
        """Su invitación aún aceptable a esa competición, la más reciente: solo id y caducidad."""
        suyas = [
            inv
            for inv in self._invitations.values()
            if inv.competition_id == competition_id and _suya_y_aceptable(inv, user_id, email, now)
        ]
        inv = max(suyas, key=lambda inv: inv.created_at, default=None)
        return InvitacionPendiente(inv.id, inv.expires_at) if inv else None

    async def find_pending_by_competition(self, competition_id: CompetitionId) -> list[Invitation]:
        return [
            inv
            for inv in self._invitations.values()
            if inv.competition_id == competition_id and inv.status == InvitationStatus.PENDING
        ]

    async def find_pending_by_email_and_competition(
        self, email: str, competition_id: CompetitionId
    ) -> Invitation | None:
        normalized_email = email.strip().lower()
        for inv in self._invitations.values():
            if (
                inv.invitee_email == normalized_email
                and inv.competition_id == competition_id
                and inv.status == InvitationStatus.PENDING
            ):
                return inv
        return None

    async def count_by_competition(
        self,
        competition_id: CompetitionId,
        status: InvitationStatus | None = None,
        since: datetime | None = None,
    ) -> int:
        return sum(
            1
            for inv in self._invitations.values()
            if inv.competition_id == competition_id
            and (status is None or inv.status == status)
            and (since is None or inv.created_at >= since)
        )

    async def count_by_invitee(
        self,
        email: str | None = None,
        user_id: UserId | None = None,
        status: InvitationStatus | None = None,
    ) -> int:
        count = 0
        for inv in self._invitations.values():
            if status and inv.status != status:
                continue
            if (email and inv.invitee_email == email.strip().lower()) or (
                user_id and inv.invitee_user_id == user_id
            ):
                count += 1
        return count
