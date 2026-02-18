"""Caso de Uso: Listar Mis Invitaciones (como invitado)."""

from src.modules.competition.application.dto.invitation_dto import (
    InvitationResponseDTO,
    PaginatedInvitationResponseDTO,
)
from src.modules.competition.domain.repositories.competition_unit_of_work_interface import (
    CompetitionUnitOfWorkInterface,
)
from src.modules.competition.domain.value_objects.invitation_status import InvitationStatus
from src.modules.user.domain.repositories.user_unit_of_work_interface import (
    UserUnitOfWorkInterface,
)
from src.modules.user.domain.value_objects.user_id import UserId


class ListMyInvitationsUseCase:
    """Lista las invitaciones recibidas por el usuario actual."""

    def __init__(
        self,
        uow: CompetitionUnitOfWorkInterface,
        user_uow: UserUnitOfWorkInterface,
    ):
        self._uow = uow
        self._user_uow = user_uow

    async def execute(
        self,
        user_id: str,
        status_filter: str | None = None,
        page: int = 1,
        limit: int = 20,
    ) -> PaginatedInvitationResponseDTO:
        user_id_vo = UserId(user_id)
        offset = (page - 1) * limit

        # Parsear status filter
        status_vo = InvitationStatus(status_filter) if status_filter else None

        # Obtener email del usuario
        async with self._user_uow:
            user = await self._user_uow.users.find_by_id(user_id_vo)
            user_email = str(user.email) if user else None

        async with self._uow:
            # Buscar por email (cubre invitaciones pre-registro)
            invitations_by_email = []
            if user_email:
                invitations_by_email = await self._uow.invitations.find_by_invitee_email(
                    user_email, status=status_vo, limit=limit + offset + 50, offset=0
                )

            # Buscar por user_id (cubre invitaciones donde el user_id fue resuelto)
            invitations_by_user_id = await self._uow.invitations.find_by_invitee_user_id(
                user_id_vo, status=status_vo, limit=limit + offset + 50, offset=0
            )

            # Merge y deduplicar por ID
            seen_ids = set()
            all_invitations = []
            for inv in invitations_by_email + invitations_by_user_id:
                if inv.id not in seen_ids:
                    seen_ids.add(inv.id)
                    # Check expiration on-read
                    inv.check_expiration()
                    # Si filtramos por status, verificar despues de expiracion
                    if status_vo and inv.status != status_vo:
                        continue
                    all_invitations.append(inv)

            # Total count (despues de filtro)
            total_count = len(all_invitations)

            # Paginar
            paginated = all_invitations[offset : offset + limit]

            # Enriquecer con nombres
            invitation_dtos = []
            for inv in paginated:
                dto = await self._enrich_invitation(inv)
                invitation_dtos.append(dto)

        return PaginatedInvitationResponseDTO(
            invitations=invitation_dtos,
            total_count=total_count,
            page=page,
            limit=limit,
        )

    async def _enrich_invitation(self, invitation) -> InvitationResponseDTO:
        """Enriquece una invitation con nombres resueltos."""
        # Resolver competition_name
        competition = await self._uow.competitions.find_by_id(invitation.competition_id)
        competition_name = str(competition.name) if competition else "Unknown"

        # Resolver inviter_name
        async with self._user_uow:
            inviter_user = await self._user_uow.users.find_by_id(invitation.inviter_id)
            inviter_name = (
                f"{inviter_user.first_name} {inviter_user.last_name}"
                if inviter_user
                else "Unknown"
            )

            # Resolver invitee_name
            invitee_name = None
            if invitation.invitee_user_id:
                invitee_user = await self._user_uow.users.find_by_id(
                    invitation.invitee_user_id
                )
                if invitee_user:
                    invitee_name = f"{invitee_user.first_name} {invitee_user.last_name}"

        return InvitationResponseDTO(
            id=invitation.id.value,
            competition_id=invitation.competition_id.value,
            competition_name=competition_name,
            inviter_id=invitation.inviter_id.value,
            inviter_name=inviter_name,
            invitee_email=invitation.invitee_email,
            invitee_user_id=(
                invitation.invitee_user_id.value if invitation.invitee_user_id else None
            ),
            invitee_name=invitee_name,
            status=invitation.status.value,
            personal_message=invitation.personal_message,
            expires_at=invitation.expires_at,
            responded_at=invitation.responded_at,
            created_at=invitation.created_at,
            updated_at=invitation.updated_at,
        )
