"""Draft Repository Interface - Domain Layer (FE #653)."""

from abc import ABC, abstractmethod

from src.modules.competition.domain.entities.draft import Draft
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.user.domain.value_objects.user_id import UserId


class DraftRepositoryInterface(ABC):
    """Interfaz para el repositorio de salas de draft."""

    @abstractmethod
    async def add(self, draft: Draft) -> None:
        """Guarda una sala nueva."""
        pass

    @abstractmethod
    async def update(self, draft: Draft) -> None:
        """Guarda los cambios de una sala."""
        pass

    @abstractmethod
    async def find_by_competition(self, competition_id: CompetitionId) -> Draft | None:
        """La sala de esa competición, o None si no se ha abierto."""
        pass

    @abstractmethod
    async def find_by_competition_for_update(self, competition_id: CompetitionId) -> Draft | None:
        """La sala con su fila bloqueada (SELECT ... FOR UPDATE).

        Elegir es una carrera de verdad: dos capitanes pueden pulsar a la vez, y
        el turno agotado lo resuelve quien mire la sala, así que varias miradas
        simultáneas podrían elegir dos veces por el mismo turno.
        """
        pass

    @abstractmethod
    async def exists_by_captain(self, user_id: UserId) -> bool:
        """Si esa persona capitanea alguna sala de draft.

        Lo pregunta el borrado de usuarios: una sala sin capitan no existe, asi
        que el panel de administracion tiene que decir «tiene actividad» en vez
        de estrellarse contra la clave ajena.
        """
        pass
