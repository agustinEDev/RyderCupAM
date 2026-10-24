"""Adaptador: `quick_match` publica sus logros a traves del modulo social."""

import logging
from datetime import datetime

from src.modules.quick_match.application.ports.round_achievements_publisher_interface import (
    RoundAchievementsPublisherInterface,
)
from src.modules.social.application.use_cases.publish_quick_match_result_use_case import (
    PublishQuickMatchResultUseCase,
)
from src.modules.social.application.use_cases.publish_round_achievements_use_case import (
    PublishRoundAchievementsUseCase,
)

logger = logging.getLogger(__name__)


class QuickMatchAchievementsPublisher(RoundAchievementsPublisherInterface):
    """
    Une los dos modulos sin que ninguno importe al otro.

    `quick_match` conoce solo su puerto; `social` conoce solo su caso de uso.
    Este adaptador vive en infraestructura, que es donde el proyecto permite
    conocer ambos lados.

    Al cerrar la partida publica dos cosas: los logros de cada vuelta y como
    acabo cada jugador (BE-2). Cada una por su lado: si una falla, la otra sale
    igual, y ninguna tumba el cierre.
    """

    def __init__(
        self,
        publish_use_case: PublishRoundAchievementsUseCase,
        result_use_case: PublishQuickMatchResultUseCase | None = None,
    ):
        self._publish = publish_use_case
        self._result = result_use_case

    async def publish(self, quick_match_id: str, published_at: datetime | None = None) -> int:
        publicados = 0
        try:
            publicados += await self._publish.execute(quick_match_id, published_at=published_at)
        except Exception:
            logger.warning(
                "Could not publish achievements for quick match %s", quick_match_id, exc_info=True
            )
        if self._result is not None:
            try:
                publicados += await self._result.execute(quick_match_id, published_at=published_at)
            except Exception:
                logger.warning(
                    "Could not publish the result of quick match %s", quick_match_id, exc_info=True
                )
        return publicados
