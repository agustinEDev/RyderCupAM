"""Adaptador: `competition` publica sus logros a traves del modulo social."""

import logging

from src.modules.competition.application.ports.tournament_achievements_publisher_interface import (
    TournamentAchievementsPublisherInterface,
)
from src.modules.social.application.use_cases.publish_tournament_achievements_use_case import (
    PublishTournamentAchievementsUseCase,
)

logger = logging.getLogger(__name__)


class TournamentAchievementsPublisher(TournamentAchievementsPublisherInterface):
    """
    Une `competition` con el feed sin que ninguno importe al otro.

    Mismo reparto que en las partidas rapidas: el modulo que cierra la vuelta
    conoce solo su puerto, y el adaptador —que vive en infraestructura— es el
    unico que ve los dos lados.
    """

    def __init__(self, publish_use_case: PublishTournamentAchievementsUseCase):
        self._publish = publish_use_case

    async def publish(self, competition_id: str) -> int:
        publicados = await self._publish.execute(competition_id)
        # Y los del mismo dia ya cerrados, que dependen de este (revision final
        # de bugs, 22 oct 2026). Con fallo seguro: lo propio ya esta publicado
        try:
            await self._publish.republish_same_day(competition_id)
        except Exception:
            logger.warning(
                "Could not republish the same-day tournaments of %s", competition_id, exc_info=True
            )
        return publicados
