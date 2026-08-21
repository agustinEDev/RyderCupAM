"""Caso de Uso: Volver a mostrar una partida rapida ocultada del propio historial."""

from src.modules.quick_match.application.dto.quick_match_dto import (
    HideQuickMatchRequestDTO,
    QuickMatchResponseDTO,
)
from src.modules.quick_match.application.exceptions import QuickMatchNotFoundError
from src.modules.quick_match.application.mappers.quick_match_mapper import QuickMatchDTOMapper
from src.modules.quick_match.domain.repositories.quick_match_unit_of_work_interface import (
    QuickMatchUnitOfWorkInterface,
)
from src.modules.quick_match.domain.value_objects.participant_id import ParticipantId
from src.modules.quick_match.domain.value_objects.quick_match_id import QuickMatchId
from src.modules.user.domain.repositories.user_unit_of_work_interface import (
    UserUnitOfWorkInterface,
)
from src.modules.user.domain.value_objects.user_id import UserId


class UnhideQuickMatchUseCase:
    """Contrario de HideQuickMatchUseCase: vuelve a mostrar la partida en el historial propio."""

    def __init__(self, uow: QuickMatchUnitOfWorkInterface, user_uow: UserUnitOfWorkInterface):
        self._uow = uow
        self._user_uow = user_uow

    async def execute(self, request: HideQuickMatchRequestDTO) -> QuickMatchResponseDTO:
        requester_id = UserId(request.requester_id)
        requester_participant_id = ParticipantId(requester_id.value)

        async with self._uow:
            quick_match = await self._uow.quick_matches.find_by_id_for_update(
                QuickMatchId(request.quick_match_id)
            )
            if not quick_match:
                raise QuickMatchNotFoundError(f"Quick match not found: {request.quick_match_id}")

            quick_match.unhide_for(requester_participant_id)
            await self._uow.quick_matches.update(quick_match)

        return await QuickMatchDTOMapper.to_response_dto(
            quick_match, self._user_uow, requester_id=requester_id
        )
