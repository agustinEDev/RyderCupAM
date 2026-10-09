"""Repositorio: las partidas de las franjas de stroke play (#251, PR 4)."""

from abc import ABC, abstractmethod
from collections.abc import Sequence

from src.modules.competition.domain.entities.partida import Partida
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.partida_id import PartidaId
from src.modules.competition.domain.value_objects.round_id import RoundId
from src.modules.user.domain.value_objects.user_id import UserId


class PartidaRepositoryInterface(ABC):
    """Cada partida con sus jugadores; un jugador está como mucho en una por franja."""

    @abstractmethod
    async def reemplazar_franja(self, round_id: RoundId, partidas: Sequence[Partida]) -> None:
        """Deja la franja con estas partidas y ninguna más (al generar)."""

    @abstractmethod
    async def anadir(self, partidas: Sequence[Partida]) -> None:
        """Añade partidas nuevas a su franja (una nueva al final, al mover)."""

    @abstractmethod
    async def guardar(self, partidas: Sequence[Partida]) -> None:
        """
        Guarda los cambios de partidas que ya existen: jugadores, marcadores,
        número. Se guardan juntas porque un intercambio o un reordenado solo es
        válido completo: a medias, un jugador o un número estaría repetido.
        """

    @abstractmethod
    async def borrar(self, partidas: Sequence[Partida]) -> None:
        """Borra estas partidas."""

    @abstractmethod
    async def find_by_id(self, partida_id: PartidaId) -> Partida | None:
        """Una partida, o None si no existe."""

    @abstractmethod
    async def find_by_id_for_update(self, partida_id: PartidaId) -> Partida | None:
        """Una partida, bloqueada hasta el final de la transacción (anotar y entregar)."""

    @abstractmethod
    async def de_la_franja(self, round_id: RoundId) -> list[Partida]:
        """Las partidas de la franja, por número de salida."""

    @abstractmethod
    async def de_la_competicion(self, competition_id: CompetitionId) -> list[Partida]:
        """Todas las partidas de la competición, por franja y número de salida."""

    @abstractmethod
    async def del_jugador(self, competition_id: CompetitionId, user_id: UserId) -> list[Partida]:
        """Las partidas de la competición en las que juega, por franja y número."""

    @abstractmethod
    async def existe_con_jugador(self, user_id: UserId) -> bool:
        """Si juega en alguna partida, de cualquier competición (antes de borrar al usuario)."""
