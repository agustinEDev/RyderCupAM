"""In-Memory TeamAssignment Repository para testing."""

from src.modules.competition.domain.entities.team_assignment import TeamAssignment
from src.modules.competition.domain.repositories.team_assignment_repository_interface import (
    TeamAssignmentRepositoryInterface,
)
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.team_assignment_id import (
    TeamAssignmentId,
)


class InMemoryTeamAssignmentRepository(TeamAssignmentRepositoryInterface):
    """Implementacion en memoria del repositorio de asignaciones para testing."""

    def __init__(self):
        self._assignments: dict[TeamAssignmentId, TeamAssignment] = {}

    async def add(self, assignment: TeamAssignment) -> None:
        self._assignments[assignment.id] = assignment

    async def find_by_id(self, assignment_id: TeamAssignmentId) -> TeamAssignment | None:
        return self._assignments.get(assignment_id)

    async def find_by_competition(self, competition_id: CompetitionId) -> TeamAssignment | None:
        for assignment in self._assignments.values():
            if assignment.competition_id == competition_id:
                return assignment
        return None

    async def delete(self, assignment_id: TeamAssignmentId) -> bool:
        if assignment_id in self._assignments:
            del self._assignments[assignment_id]
            return True
        return False
