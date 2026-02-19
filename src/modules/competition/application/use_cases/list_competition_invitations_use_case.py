"""Caso de Uso: Listar Invitaciones de una Competicion (para el creator)."""

from src.modules.competition.application.dto.invitation_dto import (
    InvitationResponseDTO,
    PaginatedInvitationResponseDTO,
)
from src.modules.competition.application.exceptions import (
    CompetitionNotFoundError,
    NotCompetitionCreatorError,
)
from src.modules.competition.domain.repositories.competition_unit_of_work_interface import (
    CompetitionUnitOfWorkInterface,
)
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.invitation_status import InvitationStatus
from src.modules.user.domain.repositories.user_unit_of_work_interface import (
    UserUnitOfWorkInterface,
)
from src.modules.user.domain.value_objects.user_id import UserId


class ListCompetitionInvitationsUseCase:
    """Lista las invitaciones de una competicion (vista del creator)."""

    def __init__(
        self,
        uow: CompetitionUnitOfWorkInterface,
        user_uow: UserUnitOfWorkInterface,
    ):
        self._uow = uow
        self._user_uow = user_uow

    async def execute(
        self,
        competition_id: str,
        current_user_id: str,
        is_admin: bool = False,
        status_filter: str | None = None,
        page: int = 1,
        limit: int = 20,
    ) -> PaginatedInvitationResponseDTO:
        competition_id_vo = CompetitionId(competition_id)
        creator_id = UserId(current_user_id)
        offset = (page - 1) * limit

        # Parsear status filter
        status_vo = InvitationStatus(status_filter) if status_filter else None

        async with self._uow:
            # 1. Buscar competition
            competition = await self._uow.competitions.find_by_id(competition_id_vo)
            if not competition:
                raise CompetitionNotFoundError(
                    f"Competition not found: {competition_id}"
                )

            # 2. Verificar creator/admin
            if not is_admin and not competition.is_creator(creator_id):
                raise NotCompetitionCreatorError(
                    "Only the competition creator or an administrator can view invitations."
                )

            # 3. Obtener invitaciones con over-fetch para compensar expiraciones
            fetch_limit = max(limit * 2, limit + 10)
            invitations = await self._uow.invitations.find_by_competition(
                competition_id_vo, status=status_vo, limit=fetch_limit, offset=offset
            )

            # 4. Check expiration on-read para PENDING y persistir cambios
            expired_invitations = []
            for inv in invitations:
                old_status = inv.status
                inv.check_expiration()
                if inv.status != old_status:
                    expired_invitations.append(inv)

            # Persistir invitaciones cuyo status cambio a EXPIRED
            for inv in expired_invitations:
                await self._uow.invitations.update(inv)

            # Filtrar de nuevo si el status cambio por expiracion y recortar a limit
            if status_vo:
                invitations = [inv for inv in invitations if inv.status == status_vo]
            invitations = invitations[:limit]

            # 5. Total count (consistente con filtro post-expiracion)
            total_count = await self._uow.invitations.count_by_competition(
                competition_id_vo, status=status_vo
            )

            # 6. Guardar datos intermedios
            competition_name = str(competition.name)

        # 7. Enriquecer con nombres en una sola sesion de usuario
        invitation_dtos = []
        async with self._user_uow:
            for inv in invitations:
                inviter_user = await self._user_uow.users.find_by_id(inv.inviter_id)
                inviter_name = (
                    f"{inviter_user.first_name} {inviter_user.last_name}"
                    if inviter_user
                    else "Unknown"
                )

                invitee_name = None
                if inv.invitee_user_id:
                    invitee_user = await self._user_uow.users.find_by_id(
                        inv.invitee_user_id
                    )
                    if invitee_user:
                        invitee_name = (
                            f"{invitee_user.first_name} {invitee_user.last_name}"
                        )

                invitation_dtos.append(
                    InvitationResponseDTO(
                        id=inv.id.value,
                        competition_id=inv.competition_id.value,
                        competition_name=competition_name,
                        inviter_id=inv.inviter_id.value,
                        inviter_name=inviter_name,
                        invitee_email=inv.invitee_email,
                        invitee_user_id=(
                            inv.invitee_user_id.value if inv.invitee_user_id else None
                        ),
                        invitee_name=invitee_name,
                        status=inv.status.value,
                        personal_message=inv.personal_message,
                        expires_at=inv.expires_at,
                        responded_at=inv.responded_at,
                        created_at=inv.created_at,
                        updated_at=inv.updated_at,
                    )
                )

        return PaginatedInvitationResponseDTO(
            invitations=invitation_dtos,
            total_count=total_count,
            page=page,
            limit=limit,
        )
