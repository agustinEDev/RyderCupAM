"""Match Repository Interface - Domain Layer."""

from abc import ABC, abstractmethod

from ..entities.match import Match
from ..value_objects.match_id import MatchId
from ..value_objects.round_id import RoundId


class MatchRepositoryInterface(ABC):
    """Interfaz para el repositorio de partidos."""

    @abstractmethod
    async def add(self, match: Match) -> None:
        """Agrega un nuevo partido."""
        pass

    @abstractmethod
    async def update(self, match: Match) -> None:
        """Actualiza un partido existente."""
        pass

    @abstractmethod
    async def find_by_id(self, match_id: MatchId) -> Match | None:
        """Busca un partido por su ID."""
        pass

    @abstractmethod
    async def find_by_round(self, round_id: RoundId) -> list[Match]:
        """Busca todos los partidos de una ronda."""
        pass

    @abstractmethod
    async def delete(self, match_id: MatchId) -> bool:
        """Elimina un partido. Retorna True si existia."""
        pass
