"""Tests para InMemoryRoundRepository."""

from datetime import date

import pytest

from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.round_id import RoundId
from src.modules.competition.domain.value_objects.session_type import SessionType
from src.modules.competition.infrastructure.persistence.in_memory.in_memory_round_repository import (
    InMemoryRoundRepository,
)
from src.modules.golf_course.domain.value_objects.golf_course_id import GolfCourseId
from tests.unit.modules.competition.infrastructure.persistence.helpers import (
    create_round,
)


class TestInMemoryRoundRepository:
    """Tests para el repositorio en memoria de Rounds."""

    def setup_method(self):
        self.repo = InMemoryRoundRepository()
        self.competition_id = CompetitionId.generate()
        self.golf_course_id = GolfCourseId.generate()

    @pytest.mark.asyncio
    async def test_add_and_find_by_id(self):
        """Agregar y encontrar un round por ID."""
        round_entity = create_round(
            competition_id=self.competition_id,
            golf_course_id=self.golf_course_id,
        )
        await self.repo.add(round_entity)

        found = await self.repo.find_by_id(round_entity.id)
        assert found is not None
        assert found.id == round_entity.id

    @pytest.mark.asyncio
    async def test_find_by_id_not_found(self):
        """Retorna None si el ID no existe."""
        result = await self.repo.find_by_id(RoundId.generate())
        assert result is None

    @pytest.mark.asyncio
    async def test_update(self):
        """Actualizar un round existente."""
        round_entity = create_round(
            competition_id=self.competition_id,
            golf_course_id=self.golf_course_id,
        )
        await self.repo.add(round_entity)

        round_entity.mark_teams_assigned()
        await self.repo.update(round_entity)

        found = await self.repo.find_by_id(round_entity.id)
        assert found is not None
        from src.modules.competition.domain.value_objects.round_status import RoundStatus
        assert found.status == RoundStatus.PENDING_MATCHES

    @pytest.mark.asyncio
    async def test_find_by_competition(self):
        """Encontrar rounds por competition_id."""
        other_comp_id = CompetitionId.generate()

        round_1 = create_round(competition_id=self.competition_id, golf_course_id=self.golf_course_id)
        round_2 = create_round(
            competition_id=self.competition_id,
            golf_course_id=self.golf_course_id,
            session_type=SessionType.AFTERNOON,
        )
        round_3 = create_round(competition_id=other_comp_id, golf_course_id=self.golf_course_id)

        await self.repo.add(round_1)
        await self.repo.add(round_2)
        await self.repo.add(round_3)

        result = await self.repo.find_by_competition(self.competition_id)
        assert len(result) == 2
        ids = {r.id for r in result}
        assert round_1.id in ids
        assert round_2.id in ids

    @pytest.mark.asyncio
    async def test_find_by_competition_and_date(self):
        """Encontrar rounds por competition_id y fecha."""
        date_1 = date(2026, 3, 15)
        date_2 = date(2026, 3, 16)

        round_1 = create_round(
            competition_id=self.competition_id,
            golf_course_id=self.golf_course_id,
            round_date=date_1,
        )
        round_2 = create_round(
            competition_id=self.competition_id,
            golf_course_id=self.golf_course_id,
            round_date=date_2,
            session_type=SessionType.AFTERNOON,
        )

        await self.repo.add(round_1)
        await self.repo.add(round_2)

        result = await self.repo.find_by_competition_and_date(self.competition_id, date_1)
        assert len(result) == 1
        assert result[0].id == round_1.id

    @pytest.mark.asyncio
    async def test_delete_existing(self):
        """Eliminar un round existente retorna True."""
        round_entity = create_round(
            competition_id=self.competition_id,
            golf_course_id=self.golf_course_id,
        )
        await self.repo.add(round_entity)

        result = await self.repo.delete(round_entity.id)
        assert result is True
        assert await self.repo.find_by_id(round_entity.id) is None

    @pytest.mark.asyncio
    async def test_delete_non_existing(self):
        """Eliminar un round inexistente retorna False."""
        result = await self.repo.delete(RoundId.generate())
        assert result is False
