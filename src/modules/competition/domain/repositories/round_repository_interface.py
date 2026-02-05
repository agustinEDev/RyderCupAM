"""Round Repository Interface - Domain Layer."""

from abc import ABC, abstractmethod
from datetime import date

from ..entities.round import Round
from ..value_objects.competition_id import CompetitionId
from ..value_objects.round_id import RoundId


class RoundRepositoryInterface(ABC):
    """Interfaz para el repositorio de rondas."""

    @abstractmethod
    async def add(self, round: Round) -> None:
        """Agrega una nueva ronda."""
        pass

    @abstractmethod
    async def update(self, round: Round) -> None:
        """Actualiza una ronda existente."""
        pass

    @abstractmethod
    async def find_by_id(self, round_id: RoundId) -> Round | None:
        """Busca una ronda por su ID."""
        pass

    @abstractmethod
    async def find_by_competition(
        self, competition_id: CompetitionId
    ) -> list[Round]:
        """Busca todas las rondas de una competicion."""
        pass

    @abstractmethod
    async def find_by_competition_and_date(
        self, competition_id: CompetitionId, round_date: date
    ) -> list[Round]:
        """Busca rondas de una competicion en una fecha especifica."""
        pass

    @abstractmethod
    async def delete(self, round_id: RoundId) -> bool:
        """Elimina una ronda. Retorna True si existia."""
        pass
