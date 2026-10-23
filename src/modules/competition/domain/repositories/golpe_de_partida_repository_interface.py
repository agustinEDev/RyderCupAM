"""Repositorio: los golpes de los jugadores de las partidas de stroke play (#251, PR 5)."""

from abc import ABC, abstractmethod

from src.modules.competition.domain.entities.golpe_de_partida import GolpeDePartida
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.partida_id import PartidaId
from src.modules.competition.domain.value_objects.round_id import RoundId
from src.modules.user.domain.value_objects.user_id import UserId


class GolpeDePartidaRepositoryInterface(ABC):
    """Un golpe por jugador, partida y hoyo."""

    @abstractmethod
    async def guardar(self, golpe: GolpeDePartida) -> None:
        """Lo crea, o lo actualiza si ese hoyo de ese jugador ya existe."""

    @abstractmethod
    async def de_la_partida(self, partida_id: PartidaId) -> list[GolpeDePartida]:
        """Los de una partida, por jugador y hoyo."""

    @abstractmethod
    async def de_la_franja(self, round_id: RoundId) -> list[GolpeDePartida]:
        """Los de todas las partidas de una franja (su clasificación)."""

    @abstractmethod
    async def de_la_competicion(self, competition_id: CompetitionId) -> list[GolpeDePartida]:
        """Los de toda la competición (la general)."""

    @abstractmethod
    async def de_las_partidas(self, partida_ids: list[PartidaId]) -> list[GolpeDePartida]:
        """Los de varias partidas en una sola lectura, no una por partida (BE-3)."""

    @abstractmethod
    async def hoyos_jugados(
        self, partida_ids: list[PartidaId]
    ) -> dict[tuple[PartidaId, UserId], int]:
        """
        Cuantos hoyos tiene apuntados cada jugador en esas partidas (la raya
        tambien), solo los que tienen alguno. En una sola lectura.
        """
