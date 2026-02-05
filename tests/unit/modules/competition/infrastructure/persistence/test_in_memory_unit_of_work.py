"""Tests para InMemoryUnitOfWork - nuevas properties Block 5."""

import pytest

from src.modules.competition.domain.repositories.match_repository_interface import (
    MatchRepositoryInterface,
)
from src.modules.competition.domain.repositories.round_repository_interface import (
    RoundRepositoryInterface,
)
from src.modules.competition.domain.repositories.team_assignment_repository_interface import (
    TeamAssignmentRepositoryInterface,
)
from src.modules.competition.infrastructure.persistence.in_memory.in_memory_unit_of_work import (
    InMemoryUnitOfWork,
)


class TestInMemoryUnitOfWorkBlock5:
    """Tests para verificar las nuevas properties del UoW."""

    def setup_method(self):
        self.uow = InMemoryUnitOfWork()

    def test_rounds_property_returns_correct_interface(self):
        """La property rounds retorna RoundRepositoryInterface."""
        assert isinstance(self.uow.rounds, RoundRepositoryInterface)

    def test_matches_property_returns_correct_interface(self):
        """La property matches retorna MatchRepositoryInterface."""
        assert isinstance(self.uow.matches, MatchRepositoryInterface)

    def test_team_assignments_property_returns_correct_interface(self):
        """La property team_assignments retorna TeamAssignmentRepositoryInterface."""
        assert isinstance(self.uow.team_assignments, TeamAssignmentRepositoryInterface)

    @pytest.mark.asyncio
    async def test_context_manager_with_new_repos(self):
        """El UoW funciona como context manager con los nuevos repos."""
        async with self.uow as uow:
            assert uow.rounds is not None
            assert uow.matches is not None
            assert uow.team_assignments is not None
        assert self.uow.committed is True
