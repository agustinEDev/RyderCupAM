"""Caso de Uso: Cancelar una Partida Rapida."""

from src.modules.quick_match.application.dto.quick_match_dto import QuickMatchResponseDTO
from src.modules.quick_match.application.exceptions import (
    NotQuickMatchCreatorError,
    QuickMatchNotFoundError,
)
from src.modules.quick_match.application.mappers.quick_match_mapper import QuickMatchDTOMapper
from src.modules.quick_match.domain.repositories.quick_match_unit_of_work_interface import (
    QuickMatchUnitOfWorkInterface,
)
from src.modules.quick_match.domain.value_objects.quick_match_id import QuickMatchId
from src.modules.user.domain.repositories.user_unit_of_work_interface import (
    UserUnitOfWorkInterface,
)
from src.modules.user.domain.value_objects.user_id import UserId


class CancelQuickMatchUseCase:
    """El creador cancela la partida."""

    def __init__(self, uow: QuickMatchUnitOfWorkInterface, user_uow: UserUnitOfWorkInterface):
        self._uow = uow
        self._user_uow = user_uow

    async def execute(
        self, quick_match_id_raw: str, requester_id_raw: str
    ) -> QuickMatchResponseDTO:
        requester_id = UserId(requester_id_raw)

        async with self._uow:
            quick_match = await self._uow.quick_matches.find_by_id(
                QuickMatchId(quick_match_id_raw)
            )
            if not quick_match:
                raise QuickMatchNotFoundError(f"Quick match not found: {quick_match_id_raw}")

            if quick_match.creator_id != requester_id:
                raise NotQuickMatchCreatorError("Only the creator can cancel the quick match.")

            quick_match.cancel()
            await self._uow.quick_matches.update(quick_match)

        return await QuickMatchDTOMapper.to_response_dto(quick_match, self._user_uow)
