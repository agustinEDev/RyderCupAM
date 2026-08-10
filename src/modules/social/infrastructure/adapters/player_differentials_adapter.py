"""Adaptador: el mejor diferencial sale del modulo de estadisticas."""

from src.modules.social.application.ports.player_differentials_interface import (
    PlayerDifferentialsInterface,
)
from src.modules.user.application.use_cases.get_player_stats_use_case import (
    GetPlayerStatsUseCase,
)
from src.modules.user.domain.value_objects.user_id import UserId


class StatsPlayerDifferentialsAdapter(PlayerDifferentialsInterface):
    """
    Implementa el puerto delegando en las estadisticas del jugador (BE #167).

    El diferencial no se recalcula aqui: el WHS ya esta implementado una vez, en
    `GetPlayerStatsUseCase`, y tener una segunda implementacion solo para el feed
    garantizaria que las dos se separaran con el tiempo. El adaptador vive en
    infraestructura precisamente para que el caso de uso del feed no sepa de que
    modulo sale el numero.
    """

    def __init__(self, stats_use_case: GetPlayerStatsUseCase):
        self._stats = stats_use_case

    async def best_differential(self, user_id: UserId) -> float | None:
        stats = await self._stats.execute(user_id)
        return stats.best_differential
