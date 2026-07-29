"""Caso de Uso: Editar el handicap de un participante antes de iniciar la partida."""

from src.modules.quick_match.application.dto.quick_match_dto import (
    QuickMatchResponseDTO,
    SetParticipantHandicapRequestDTO,
)
from src.modules.quick_match.application.exceptions import (
    NotQuickMatchCreatorError,
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


class SetParticipantHandicapUseCase:
    """
    Edita el handicap de un participante (manual para invitados, override para
    registrados) mientras la partida esta PENDING — pensado para el resumen
    previo a `start()`.

    Solo el creador puede editarlo.
    """

    def __init__(self, uow: QuickMatchUnitOfWorkInterface, user_uow: UserUnitOfWorkInterface):
        self._uow = uow
        self._user_uow = user_uow

    async def execute(self, request: SetParticipantHandicapRequestDTO) -> QuickMatchResponseDTO:
        requester_id = UserId(request.requester_id)
        target_participant_id = ParticipantId(request.target_participant_id)

        async with self._uow:
            quick_match = await self._uow.quick_matches.find_by_id_for_update(
                QuickMatchId(request.quick_match_id)
            )
            if not quick_match:
                raise QuickMatchNotFoundError(f"Quick match not found: {request.quick_match_id}")

            if quick_match.creator_id != requester_id:
                raise NotQuickMatchCreatorError(
                    "Only the quick match creator can edit a participant's handicap."
                )

            quick_match.set_participant_handicap(target_participant_id, request.handicap)
            await self._uow.quick_matches.update(quick_match)

        return await QuickMatchDTOMapper.to_response_dto(quick_match, self._user_uow)
