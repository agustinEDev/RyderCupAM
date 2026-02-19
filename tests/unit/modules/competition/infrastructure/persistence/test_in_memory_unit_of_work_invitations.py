"""Tests para InMemoryUnitOfWork - invitations property."""

import pytest

from src.modules.competition.domain.repositories.invitation_repository_interface import (
    InvitationRepositoryInterface,
)
from src.modules.competition.infrastructure.persistence.in_memory.in_memory_unit_of_work import (
    InMemoryUnitOfWork,
)


class TestInMemoryUnitOfWorkInvitations:
    """Tests para verificar la property invitations del UoW."""

    def setup_method(self):
        self.uow = InMemoryUnitOfWork()

    def test_invitations_property_returns_correct_interface(self):
        """La property invitations retorna InvitationRepositoryInterface."""
        assert isinstance(self.uow.invitations, InvitationRepositoryInterface)

    @pytest.mark.asyncio
    async def test_context_manager_with_invitations_repo(self):
        """El UoW funciona como context manager con el repo de invitations."""
        async with self.uow as uow:
            assert uow.invitations is not None
        assert self.uow.committed is True

    def test_invitations_repo_is_same_instance(self):
        """Multiples accesos retornan la misma instancia."""
        repo1 = self.uow.invitations
        repo2 = self.uow.invitations
        assert repo1 is repo2
