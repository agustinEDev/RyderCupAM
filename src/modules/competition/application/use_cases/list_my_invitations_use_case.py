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

_DEDUP_OVERFETCH_BUFFER = 50


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

        # Datos intermedios para enrichment
        paginated = []
        competition_names: dict[str, str] = {}
        total_count = 0

        async with self._uow:
            # Buscar por email (cubre invitaciones pre-registro)
            invitations_by_email = []
            if user_email:
                invitations_by_email = await self._uow.invitations.find_by_invitee_email(
                    user_email, status=status_vo, limit=limit + offset + _DEDUP_OVERFETCH_BUFFER, offset=0
                )

            # Buscar por user_id (cubre invitaciones donde el user_id fue resuelto)
            invitations_by_user_id = await self._uow.invitations.find_by_invitee_user_id(
                user_id_vo, status=status_vo, limit=limit + offset + _DEDUP_OVERFETCH_BUFFER, offset=0
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

            # Resolver competition_names dentro del comp UoW
            for inv in paginated:
                comp_id_str = str(inv.competition_id.value)
                if comp_id_str not in competition_names:
                    competition = await self._uow.competitions.find_by_id(
                        inv.competition_id
                    )
                    competition_names[comp_id_str] = (
                        str(competition.name) if competition else "Unknown"
                    )

        # Resolver nombres de usuarios en una sola sesion
        invitation_dtos = []
        async with self._user_uow:
            for inv in paginated:
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
                        competition_name=competition_names.get(
                            str(inv.competition_id.value), "Unknown"
                        ),
                        inviter_id=inv.inviter_id.value,
                        inviter_name=inviter_name,
                        invitee_email=inv.invitee_email,
                        invitee_user_id=(
                            inv.invitee_user_id.value
                            if inv.invitee_user_id
                            else None
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
