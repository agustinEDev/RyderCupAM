"""Repositorio: los golpes de los jugadores de las partidas de stroke play (#251, PR 5)."""

from abc import ABC, abstractmethod

from src.modules.competition.domain.entities.golpe_de_partida import GolpeDePartida
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.partida_id import PartidaId
from src.modules.competition.domain.value_objects.round_id import RoundId


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
