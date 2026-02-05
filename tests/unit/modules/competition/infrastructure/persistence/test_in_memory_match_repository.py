"""Tests para InMemoryMatchRepository."""

import pytest

from src.modules.competition.domain.value_objects.match_id import MatchId
from src.modules.competition.domain.value_objects.round_id import RoundId
from src.modules.competition.infrastructure.persistence.in_memory.in_memory_match_repository import (
    InMemoryMatchRepository,
)
from tests.unit.modules.competition.infrastructure.persistence.helpers import (
    create_match,
)


class TestInMemoryMatchRepository:
    """Tests para el repositorio en memoria de Matches."""

    def setup_method(self):
        self.repo = InMemoryMatchRepository()
        self.round_id = RoundId.generate()

    @pytest.mark.asyncio
    async def test_add_and_find_by_id(self):
        """Agregar y encontrar un match por ID."""
        match = create_match(round_id=self.round_id, match_number=1)
        await self.repo.add(match)

        found = await self.repo.find_by_id(match.id)
        assert found is not None
        assert found.id == match.id

    @pytest.mark.asyncio
    async def test_find_by_id_not_found(self):
        """Retorna None si el ID no existe."""
        result = await self.repo.find_by_id(MatchId.generate())
        assert result is None

    @pytest.mark.asyncio
    async def test_update(self):
        """Actualizar un match existente."""
        match = create_match(round_id=self.round_id, match_number=1)
        await self.repo.add(match)

        match.start()
        await self.repo.update(match)

        found = await self.repo.find_by_id(match.id)
        assert found is not None
        from src.modules.competition.domain.value_objects.match_status import MatchStatus
        assert found.status == MatchStatus.IN_PROGRESS

    @pytest.mark.asyncio
    async def test_find_by_round(self):
        """Encontrar matches por round_id."""
        other_round_id = RoundId.generate()

        match_1 = create_match(round_id=self.round_id, match_number=1)
        match_2 = create_match(round_id=self.round_id, match_number=2)
        match_3 = create_match(round_id=other_round_id, match_number=1)

        await self.repo.add(match_1)
        await self.repo.add(match_2)
        await self.repo.add(match_3)

        result = await self.repo.find_by_round(self.round_id)
        assert len(result) == 2
        ids = {m.id for m in result}
        assert match_1.id in ids
        assert match_2.id in ids

    @pytest.mark.asyncio
    async def test_delete_existing(self):
        """Eliminar un match existente retorna True."""
        match = create_match(round_id=self.round_id, match_number=1)
        await self.repo.add(match)

        result = await self.repo.delete(match.id)
        assert result is True
        assert await self.repo.find_by_id(match.id) is None

    @pytest.mark.asyncio
    async def test_delete_non_existing(self):
        """Eliminar un match inexistente retorna False."""
        result = await self.repo.delete(MatchId.generate())
        assert result is False
