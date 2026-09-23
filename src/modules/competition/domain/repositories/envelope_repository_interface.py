"""Envelope Repository Interface - Domain Layer (FE #655)."""

from abc import ABC, abstractmethod

from src.modules.competition.domain.entities.envelope import Envelope
from src.modules.competition.domain.value_objects.round_id import RoundId


class EnvelopeRepositoryInterface(ABC):
    """Interfaz para el repositorio de sobres."""

    @abstractmethod
    async def add(self, envelope: Envelope) -> None:
        """Guarda un sobre nuevo."""
        pass

    @abstractmethod
    async def update(self, envelope: Envelope) -> None:
        """Guarda los cambios de un sobre."""
        pass

    @abstractmethod
    async def find_by_round_and_team(self, round_id: RoundId, team: str) -> Envelope | None:
        """El sobre de ese equipo para esa sesión, o None si no lo hay."""
        pass

    @abstractmethod
    async def find_by_round(self, round_id: RoundId) -> list[Envelope]:
        """Los sobres de esa sesión: cero, uno o dos."""
        pass

    @abstractmethod
    async def find_by_round_and_team_for_update(
        self, round_id: RoundId, team: str
    ) -> Envelope | None:
        """El sobre con su fila bloqueada (SELECT ... FOR UPDATE).

        Entregar y rellenar automáticamente pueden coincidir: el capitán que
        pulsa «entregar» justo cuando vence el plazo no puede acabar con la
        lista de la aplicación encima de la suya.
        """
        pass
