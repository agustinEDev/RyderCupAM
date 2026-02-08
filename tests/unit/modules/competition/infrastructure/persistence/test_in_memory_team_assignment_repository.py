"""Tests para InMemoryTeamAssignmentRepository."""

import pytest

from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.team_assignment_id import (
    TeamAssignmentId,
)
from src.modules.competition.infrastructure.persistence.in_memory.in_memory_team_assignment_repository import (
    InMemoryTeamAssignmentRepository,
)
from tests.unit.modules.competition.infrastructure.persistence.helpers import (
    create_team_assignment,
)


class TestInMemoryTeamAssignmentRepository:
    """Tests para el repositorio en memoria de TeamAssignments."""

    def setup_method(self):
        self.repo = InMemoryTeamAssignmentRepository()
        self.competition_id = CompetitionId.generate()

    @pytest.mark.asyncio
    async def test_add_and_find_by_id(self):
        """Agregar y encontrar una asignación por ID."""
        assignment = create_team_assignment(competition_id=self.competition_id)
        await self.repo.add(assignment)

        found = await self.repo.find_by_id(assignment.id)
        assert found is not None
        assert found.id == assignment.id

    @pytest.mark.asyncio
    async def test_find_by_id_not_found(self):
        """Retorna None si el ID no existe."""
        result = await self.repo.find_by_id(TeamAssignmentId.generate())
        assert result is None

    @pytest.mark.asyncio
    async def test_find_by_competition(self):
        """Encontrar asignación por competition_id."""
        assignment = create_team_assignment(competition_id=self.competition_id)
        await self.repo.add(assignment)

        found = await self.repo.find_by_competition(self.competition_id)
        assert found is not None
        assert found.id == assignment.id

    @pytest.mark.asyncio
    async def test_find_by_competition_not_found(self):
        """Retorna None si no hay asignación para la competición."""
        result = await self.repo.find_by_competition(CompetitionId.generate())
        assert result is None

    @pytest.mark.asyncio
    async def test_delete_existing(self):
        """Eliminar una asignación existente retorna True."""
        assignment = create_team_assignment(competition_id=self.competition_id)
        await self.repo.add(assignment)

        result = await self.repo.delete(assignment.id)
        assert result is True
        assert await self.repo.find_by_id(assignment.id) is None

    @pytest.mark.asyncio
    async def test_delete_non_existing(self):
        """Eliminar una asignación inexistente retorna False."""
        result = await self.repo.delete(TeamAssignmentId.generate())
        assert result is False
