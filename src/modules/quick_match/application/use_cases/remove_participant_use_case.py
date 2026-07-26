"""Caso de Uso: Eliminar un participante (leave o kick por el creador)."""

from src.modules.quick_match.application.dto.quick_match_dto import (
    QuickMatchResponseDTO,
    RemoveParticipantRequestDTO,
)
from src.modules.quick_match.application.exceptions import (
    NotAuthorizedToRemoveError,
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


class RemoveParticipantUseCase:
    """
    Elimina a un participante de una partida rapida.

    Autorizacion: el propio participante (leave) o el creador (kick).
    """

    def __init__(self, uow: QuickMatchUnitOfWorkInterface, user_uow: UserUnitOfWorkInterface):
        self._uow = uow
        self._user_uow = user_uow

    async def execute(self, request: RemoveParticipantRequestDTO) -> QuickMatchResponseDTO:
        requester_id = UserId(request.requester_id)
        target_id = UserId(request.target_user_id)

        async with self._uow:
            quick_match = await self._uow.quick_matches.find_by_id(
                QuickMatchId(request.quick_match_id)
            )
            if not quick_match:
                raise QuickMatchNotFoundError(f"Quick match not found: {request.quick_match_id}")

            if requester_id not in (target_id, quick_match.creator_id):
                raise NotAuthorizedToRemoveError(
                    "Only the participant themselves or the creator can remove a participant."
                )

            quick_match.remove_participant(target_id)
            await self._uow.quick_matches.update(quick_match)

        return await QuickMatchDTOMapper.to_response_dto(quick_match, self._user_uow)
