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
            quick_match = await self._uow.quick_matches.find_by_id(
                QuickMatchId(quick_match_id_raw)
            )
            if not quick_match:
                raise QuickMatchNotFoundError(f"Quick match not found: {quick_match_id_raw}")

            if quick_match.creator_id != requester_id:
                raise NotQuickMatchCreatorError("Only the creator can complete the quick match.")

            # Antes de cerrar: una vez cerrada, esta vuelta ya cuenta para las
            # estadisticas y no habria forma de saber cual era su marca previa
            marca_previa = await self._marca_previa(quick_match)

            quick_match.complete()
            await self._uow.quick_matches.update(quick_match)

        await self._publicar_logros(quick_match_id_raw, marca_previa)

        return await QuickMatchDTOMapper.to_response_dto(quick_match, self._user_uow)

    async def _marca_previa(self, quick_match) -> dict[str, float | None]:
        """El mejor diferencial de cada jugador con cuenta, antes de cerrar."""
        if self._achievements is None:
            return {}

        user_ids = [p.user_id for p in quick_match.participants if p.user_id is not None]
        try:
            return await self._achievements.capture_best_differentials(user_ids)
        except Exception:
            # Sin marca previa se publica todo menos el record personal, que es
            # mejor que no publicar nada
            logger.warning("Could not capture differentials before completing", exc_info=True)
            return {}

    async def _publicar_logros(
        self, quick_match_id_raw: str, marca_previa: dict[str, float | None]
    ) -> None:
        """
        Publica los logros de la vuelta sin dejar que un fallo tumbe el cierre.

        La partida ya esta cerrada y guardada cuando esto corre. El feed es
        accesorio y la tarjeta no: si publicar falla, el jugador tiene que ver
        su partida terminada igualmente.
        """
        if self._achievements is None:
            return

        try:
            await self._achievements.publish(quick_match_id_raw, marca_previa)
        except Exception:
            logger.warning(
                "Could not publish achievements for quick match %s",
                quick_match_id_raw,
                exc_info=True,
            )
