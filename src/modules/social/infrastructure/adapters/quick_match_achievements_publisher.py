"""Adaptador: `quick_match` publica sus logros a traves del modulo social."""

from src.modules.quick_match.application.ports.round_achievements_publisher_interface import (
    RoundAchievementsPublisherInterface,
)
from src.modules.social.application.ports.player_differentials_interface import (
    PlayerDifferentialsInterface,
)
from src.modules.social.application.use_cases.publish_round_achievements_use_case import (
    PublishRoundAchievementsUseCase,
)
from src.modules.user.domain.value_objects.user_id import UserId


class QuickMatchAchievementsPublisher(RoundAchievementsPublisherInterface):
    """
    Une los dos modulos sin que ninguno importe al otro.

    `quick_match` conoce solo su puerto; `social` conoce solo su caso de uso.
    Este adaptador vive en infraestructura, que es donde el proyecto permite
    conocer ambos lados.
    """

    def __init__(
        self,
        publish_use_case: PublishRoundAchievementsUseCase,
        differentials: PlayerDifferentialsInterface,
    ):
        self._publish = publish_use_case
        self._differentials = differentials

    async def capture_best_differentials(
        self, user_ids: list[UserId]
    ) -> dict[str, float | None]:
        return {
            str(user_id.value): await self._differentials.best_differential(user_id)
            for user_id in user_ids
        }

    async def publish(
        self, quick_match_id: str, best_differential_before: dict[str, float | None]
    ) -> int:
        return await self._publish.execute(
            quick_match_id, best_differential_before=best_differential_before
        )
