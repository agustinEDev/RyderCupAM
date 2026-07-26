"""
QuickMatch Repository Interface - Domain Layer.
"""

from abc import ABC, abstractmethod

from src.modules.user.domain.value_objects.user_id import UserId

from ..entities.quick_match import QuickMatch
from ..value_objects.quick_match_id import QuickMatchId
from ..value_objects.quick_match_status import QuickMatchStatus


class QuickMatchRepositoryInterface(ABC):
    """Interfaz para el repositorio de partidas rapidas."""

    @abstractmethod
    async def add(self, quick_match: QuickMatch) -> None:
        pass

    @abstractmethod
    async def update(self, quick_match: QuickMatch) -> None:
        pass

    @abstractmethod
    async def find_by_id(self, quick_match_id: QuickMatchId) -> QuickMatch | None:
        pass

    @abstractmethod
    async def find_by_id_for_update(self, quick_match_id: QuickMatchId) -> QuickMatch | None:
        """
        Como `find_by_id`, pero bloqueando la fila (row-level lock) hasta el
        commit/rollback de la transaccion actual. Uso obligatorio en flujos
        de carga-y-mutacion del roster (p.ej. add_participant) para evitar
        que altas concurrentes superen el aforo del equipo.
        """
        pass

    @abstractmethod
    async def list_for_user(
        self,
        user_id: UserId,
        status: QuickMatchStatus | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> list[QuickMatch]:
        """Lista partidas rapidas en las que el usuario es participante."""
        pass

    @abstractmethod
    async def count_for_user(
        self, user_id: UserId, status: QuickMatchStatus | None = None
    ) -> int:
        pass
