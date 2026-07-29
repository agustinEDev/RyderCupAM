"""Caso de Uso: Iniciar una Partida Rapida."""

from src.modules.quick_match.application.dto.quick_match_dto import (
    QuickMatchResponseDTO,
    StartQuickMatchRequestDTO,
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


class StartQuickMatchUseCase:
    """
    El creador inicia la partida una vez el roster esta completo.

    Debe indicar `scorer_ids`: entre 1 y 4 participantes registrados (siempre
    incluyendo al creador) que seran quienes anoten los resultados. El resto
    de participantes (invitados o registrados no seleccionados) tendran su
    puntuacion registrada por delegacion.
    """

    def __init__(self, uow: QuickMatchUnitOfWorkInterface, user_uow: UserUnitOfWorkInterface):
        self._uow = uow
        self._user_uow = user_uow

    async def execute(self, request: StartQuickMatchRequestDTO) -> QuickMatchResponseDTO:
        requester_id = UserId(request.requester_id)
        scorer_ids = [ParticipantId(sid) for sid in request.scorer_ids]

        async with self._uow:
            quick_match = await self._uow.quick_matches.find_by_id(
                QuickMatchId(request.quick_match_id)
            )
            if not quick_match:
                raise QuickMatchNotFoundError(f"Quick match not found: {request.quick_match_id}")

            if quick_match.creator_id != requester_id:
                raise NotQuickMatchCreatorError("Only the creator can start the quick match.")

            quick_match.start(scorer_ids)
            await self._uow.quick_matches.update(quick_match)

        return await QuickMatchDTOMapper.to_response_dto(quick_match, self._user_uow)
