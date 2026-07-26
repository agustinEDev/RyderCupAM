"""Caso de Uso: Listar mis Partidas Rapidas."""

from src.modules.quick_match.application.dto.quick_match_dto import (
    PaginatedQuickMatchResponseDTO,
)
from src.modules.quick_match.application.mappers.quick_match_mapper import QuickMatchDTOMapper
from src.modules.quick_match.domain.repositories.quick_match_unit_of_work_interface import (
    QuickMatchUnitOfWorkInterface,
)
from src.modules.quick_match.domain.value_objects.quick_match_status import QuickMatchStatus
from src.modules.user.domain.repositories.user_unit_of_work_interface import (
    UserUnitOfWorkInterface,
)
from src.modules.user.domain.value_objects.user_id import UserId


class ListMyQuickMatchesUseCase:
    """Lista las partidas rapidas en las que el usuario actual participa."""

    def __init__(self, uow: QuickMatchUnitOfWorkInterface, user_uow: UserUnitOfWorkInterface):
        self._uow = uow
        self._user_uow = user_uow

    async def execute(
        self,
        user_id_raw: str,
        status_filter: str | None = None,
        page: int = 1,
        limit: int = 20,
    ) -> PaginatedQuickMatchResponseDTO:
        user_id = UserId(user_id_raw)
        offset = (page - 1) * limit
        status_vo = QuickMatchStatus(status_filter) if status_filter else None

        async with self._uow:
            quick_matches = await self._uow.quick_matches.list_for_user(
                user_id, status=status_vo, limit=limit, offset=offset
            )
            total_count = await self._uow.quick_matches.count_for_user(user_id, status=status_vo)

        participant_ids = list({p.user_id for qm in quick_matches for p in qm.participants})
        async with self._user_uow:
            users_by_id = {
                user.id: user for user in await self._user_uow.users.find_by_ids(participant_ids)
            }

        items = [
            await QuickMatchDTOMapper.to_response_dto(qm, self._user_uow, users_by_id=users_by_id)
            for qm in quick_matches
        ]

        return PaginatedQuickMatchResponseDTO(
            quick_matches=items,
            total_count=total_count,
            page=page,
            limit=limit,
        )
