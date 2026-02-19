"""
Invitation Repository Interface - Domain Layer.

Define el contrato para la persistencia de invitaciones siguiendo Clean Architecture.
"""

from abc import ABC, abstractmethod
from datetime import datetime

from src.modules.user.domain.value_objects.user_id import UserId

from ..entities.invitation import Invitation
from ..value_objects.competition_id import CompetitionId
from ..value_objects.invitation_id import InvitationId
from ..value_objects.invitation_status import InvitationStatus


class InvitationRepositoryInterface(ABC):
    """
    Interfaz para el repositorio de invitaciones.

    Define las operaciones CRUD y consultas especificas del dominio de invitations.
    """

    @abstractmethod
    async def add(self, invitation: Invitation) -> None:
        """Agrega una nueva invitacion al repositorio."""
        pass

    @abstractmethod
    async def update(self, invitation: Invitation) -> None:
        """Actualiza una invitacion existente en el repositorio."""
        pass

    @abstractmethod
    async def find_by_id(self, invitation_id: InvitationId) -> Invitation | None:
        """Busca una invitacion por su ID unico."""
        pass

    @abstractmethod
    async def find_by_competition(
        self,
        competition_id: CompetitionId,
        status: InvitationStatus | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> list[Invitation]:
        """Busca invitaciones de una competicion con filtro opcional de status."""
        pass

    @abstractmethod
    async def find_by_invitee_email(
        self,
        email: str,
        status: InvitationStatus | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> list[Invitation]:
        """Busca invitaciones para un email de invitado."""
        pass

    @abstractmethod
    async def find_by_invitee_user_id(
        self,
        user_id: UserId,
        status: InvitationStatus | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> list[Invitation]:
        """Busca invitaciones para un user_id de invitado."""
        pass

    @abstractmethod
    async def find_pending_by_email_and_competition(
        self, email: str, competition_id: CompetitionId
    ) -> Invitation | None:
        """Busca una invitacion PENDING para un email+competition especificos."""
        pass

    @abstractmethod
    async def count_by_competition(
        self,
        competition_id: CompetitionId,
        status: InvitationStatus | None = None,
        since: datetime | None = None,
    ) -> int:
        """Cuenta invitaciones de una competicion con filtro opcional de status y fecha."""
        pass

    @abstractmethod
    async def count_by_invitee(
        self,
        email: str | None = None,
        user_id: UserId | None = None,
        status: InvitationStatus | None = None,
    ) -> int:
        """
        Cuenta invitaciones para un invitado.

        Matches invitations where invitee_email == email OR invitee_user_id == user_id.
        If status is provided, it is applied as an additional AND filter.
        Returns 0 if neither email nor user_id is provided.
        """
        pass
