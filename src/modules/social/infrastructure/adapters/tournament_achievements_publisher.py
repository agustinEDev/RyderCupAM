"""Adaptador: `competition` publica sus logros a traves del modulo social."""

from src.modules.competition.application.ports.tournament_achievements_publisher_interface import (
    TournamentAchievementsPublisherInterface,
)
from src.modules.social.application.ports.player_differentials_interface import (
    PlayerDifferentialsInterface,
)
from src.modules.social.application.use_cases.publish_tournament_achievements_use_case import (
    PublishTournamentAchievementsUseCase,
)
from src.modules.user.domain.value_objects.user_id import UserId


class TournamentAchievementsPublisher(TournamentAchievementsPublisherInterface):
    """
    Une `competition` con el feed sin que ninguno importe al otro.

    Mismo reparto que en las partidas rapidas: el modulo que cierra la vuelta
    conoce solo su puerto, y el adaptador —que vive en infraestructura— es el
    unico que ve los dos lados.
    """

    def __init__(
        self,
        publish_use_case: PublishTournamentAchievementsUseCase,
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
        self, competition_id: str, best_differential_before: dict[str, float | None]
    ) -> int:
        return await self._publish.execute(
            competition_id, best_differential_before=best_differential_before
        )
