"""Los golpes de las partidas, en memoria para los tests (#251, PR 5)."""

from copy import deepcopy

from src.modules.competition.domain.entities.golpe_de_partida import GolpeDePartida
from src.modules.competition.domain.repositories.golpe_de_partida_repository_interface import (
    GolpeDePartidaRepositoryInterface,
)
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.partida_id import PartidaId
from src.modules.competition.domain.value_objects.round_id import RoundId
from src.modules.user.domain.value_objects.user_id import UserId


class InMemoryGolpeDePartidaRepository(GolpeDePartidaRepositoryInterface):
    """Guarda y devuelve copias, como una base de datos."""

    def __init__(self):
        self._golpes: dict[tuple[PartidaId, UserId, int], GolpeDePartida] = {}

    async def guardar(self, golpe: GolpeDePartida) -> None:
        self._golpes[(golpe.partida_id, golpe.user_id, golpe.hoyo)] = deepcopy(golpe)

    async def de_la_partida(self, partida_id: PartidaId) -> list[GolpeDePartida]:
        return self._donde(lambda g: g.partida_id == partida_id)

    async def de_la_franja(self, round_id: RoundId) -> list[GolpeDePartida]:
        return self._donde(lambda g: g.round_id == round_id)

    async def de_la_competicion(self, competition_id: CompetitionId) -> list[GolpeDePartida]:
        return self._donde(lambda g: g.competition_id == competition_id)

    def _donde(self, condicion) -> list[GolpeDePartida]:
        return [
            deepcopy(g)
            for g in sorted(
                self._golpes.values(), key=lambda g: (str(g.partida_id), str(g.user_id), g.hoyo)
            )
            if condicion(g)
        ]
