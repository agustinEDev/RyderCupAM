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
from src.modules.quick_match.domain.value_objects.participant_id import ParticipantId
from src.modules.quick_match.domain.value_objects.quick_match_id import QuickMatchId
from src.modules.user.domain.repositories.user_unit_of_work_interface import (
    UserUnitOfWorkInterface,
)
from src.modules.user.domain.value_objects.user_id import UserId


class RemoveParticipantUseCase:
    """
    Elimina a un participante de una partida rapida.

    Autorizacion: el propio participante registrado (leave) o el creador
    (kick, unica via posible para eliminar a un invitado sin cuenta).
    """

    def __init__(self, uow: QuickMatchUnitOfWorkInterface, user_uow: UserUnitOfWorkInterface):
        self._uow = uow
        self._user_uow = user_uow

    async def execute(self, request: RemoveParticipantRequestDTO) -> QuickMatchResponseDTO:
        requester_id = UserId(request.requester_id)
        requester_participant_id = ParticipantId(requester_id.value)
        target_participant_id = ParticipantId(request.target_participant_id)

        async with self._uow:
            quick_match = await self._uow.quick_matches.find_by_id_for_update(
                QuickMatchId(request.quick_match_id)
            )
            if not quick_match:
                raise QuickMatchNotFoundError(f"Quick match not found: {request.quick_match_id}")

            is_self_leave = requester_participant_id == target_participant_id
            is_creator = quick_match.creator_id == requester_id
            if not (is_self_leave or is_creator):
                raise NotAuthorizedToRemoveError(
                    "Only the participant themselves or the creator can remove a participant."
                )

            quick_match.remove_participant(target_participant_id)
            await self._uow.quick_matches.update(quick_match)

        return await QuickMatchDTOMapper.to_response_dto(quick_match, self._user_uow)
