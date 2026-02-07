"""TeamAssignment Repository Interface - Domain Layer."""

from abc import ABC, abstractmethod

from ..entities.team_assignment import TeamAssignment
from ..value_objects.competition_id import CompetitionId
from ..value_objects.team_assignment_id import TeamAssignmentId


class TeamAssignmentRepositoryInterface(ABC):
    """Interfaz para el repositorio de asignaciones de equipo."""

    @abstractmethod
    async def add(self, assignment: TeamAssignment) -> None:
        """Agrega una nueva asignacion de equipos."""
        pass

    @abstractmethod
    async def find_by_id(self, assignment_id: TeamAssignmentId) -> TeamAssignment | None:
        """Busca una asignacion por su ID."""
        pass

    @abstractmethod
    async def find_by_competition(self, competition_id: CompetitionId) -> TeamAssignment | None:
        """Busca la asignacion activa de una competicion (solo puede haber una)."""
        pass

    @abstractmethod
    async def delete(self, assignment_id: TeamAssignmentId) -> bool:
        """Elimina una asignacion. Retorna True si existia."""
        pass
