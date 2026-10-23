"""Caso de Uso: Finalizar una Partida Rapida."""

import logging

from src.modules.quick_match.application.dto.quick_match_dto import QuickMatchResponseDTO
from src.modules.quick_match.application.exceptions import (
    NotQuickMatchCreatorError,
    QuickMatchNotFoundError,
)
from src.modules.quick_match.application.mappers.quick_match_mapper import QuickMatchDTOMapper
from src.modules.quick_match.application.ports.round_achievements_publisher_interface import (
    RoundAchievementsPublisherInterface,
)
from src.modules.quick_match.domain.repositories.quick_match_unit_of_work_interface import (
    QuickMatchUnitOfWorkInterface,
)
from src.modules.quick_match.domain.value_objects.quick_match_id import QuickMatchId
from src.modules.user.domain.repositories.user_unit_of_work_interface import (
    UserUnitOfWorkInterface,
)
from src.modules.user.domain.value_objects.user_id import UserId

logger = logging.getLogger(__name__)


class CompleteQuickMatchUseCase:
    """
    El creador marca la partida como finalizada.

    Cerrar la partida es tambien lo que dispara el feed de logros (BE #175): es
    el momento en que la vuelta pasa a ser definitiva y comparable.
    """

    def __init__(
        self,
        uow: QuickMatchUnitOfWorkInterface,
        user_uow: UserUnitOfWorkInterface,
        achievements: RoundAchievementsPublisherInterface | None = None,
    ):
        self._uow = uow
        self._user_uow = user_uow
        self._achievements = achievements

    async def execute(
        self, quick_match_id_raw: str, requester_id_raw: str
    ) -> QuickMatchResponseDTO:
        requester_id = UserId(requester_id_raw)

        async with self._uow:
            # Bloqueada: el cierre automático también la escribe (23 oct 2026)
            quick_match = await self._uow.quick_matches.find_by_id_for_update(
                QuickMatchId(quick_match_id_raw)
            )
            if not quick_match:
                raise QuickMatchNotFoundError(f"Quick match not found: {quick_match_id_raw}")

            if quick_match.creator_id != requester_id:
                raise NotQuickMatchCreatorError("Only the creator can complete the quick match.")

            quick_match.complete()
            await self._uow.quick_matches.update(quick_match)

        await self._publicar_logros(quick_match_id_raw)

        return await QuickMatchDTOMapper.to_response_dto(
            quick_match, self._user_uow, requester_id=requester_id
        )

    async def _publicar_logros(self, quick_match_id_raw: str) -> None:
        """
        Publica los logros de la vuelta sin dejar que un fallo tumbe el cierre.

        La partida ya esta cerrada y guardada cuando esto corre. El feed es
        accesorio y la tarjeta no: si publicar falla, el jugador tiene que ver
        su partida terminada igualmente.
        """
        if self._achievements is None:
            return

        try:
            await self._achievements.publish(quick_match_id_raw)
        except Exception:
            logger.warning(
                "Could not publish achievements for quick match %s",
                quick_match_id_raw,
                exc_info=True,
            )
