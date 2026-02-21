"""Tests para InMemoryHoleScoreRepository."""

import pytest

from src.modules.competition.domain.entities.hole_score import HoleScore
from src.modules.competition.domain.value_objects.match_id import MatchId
from src.modules.competition.infrastructure.persistence.in_memory.in_memory_hole_score_repository import (
    InMemoryHoleScoreRepository,
)
from src.modules.user.domain.value_objects.user_id import UserId

pytestmark = pytest.mark.asyncio


def _make_hole_score(match_id=None, hole_number=1, player_user_id=None, team="A", strokes_received=0):
    """Helper para crear HoleScores."""
    return HoleScore.create(
        match_id=match_id or MatchId.generate(),
        hole_number=hole_number,
        player_user_id=player_user_id or UserId.generate(),
        team=team,
        strokes_received=strokes_received,
    )


class TestInMemoryHoleScoreRepositoryAdd:
    """Tests para add() y add_many()."""

    async def test_add_and_find_by_match(self):
        """Agregar un score y encontrarlo por match."""
        repo = InMemoryHoleScoreRepository()
        match_id = MatchId.generate()
        hs = _make_hole_score(match_id=match_id)
        await repo.add(hs)
        found = await repo.find_by_match(match_id)
        assert len(found) == 1
        assert found[0] == hs

    async def test_add_many(self):
        """Agregar multiples scores en batch."""
        repo = InMemoryHoleScoreRepository()
        match_id = MatchId.generate()
        player = UserId.generate()
        scores = [
            _make_hole_score(match_id=match_id, hole_number=h, player_user_id=player)
            for h in range(1, 4)
        ]
        await repo.add_many(scores)
        found = await repo.find_by_match(match_id)
        assert len(found) == 3


class TestInMemoryHoleScoreRepositoryFind:
    """Tests para find methods."""

    async def test_find_by_match_and_hole(self):
        """Buscar scores por match y hoyo."""
        repo = InMemoryHoleScoreRepository()
        match_id = MatchId.generate()
        a, b = UserId.generate(), UserId.generate()
        hs_a = _make_hole_score(match_id=match_id, hole_number=1, player_user_id=a)
        hs_b = _make_hole_score(match_id=match_id, hole_number=1, player_user_id=b, team="B")
        hs_other = _make_hole_score(match_id=match_id, hole_number=2, player_user_id=a)
        await repo.add(hs_a)
        await repo.add(hs_b)
        await repo.add(hs_other)

        found = await repo.find_by_match_and_hole(match_id, 1)
        assert len(found) == 2

    async def test_find_one(self):
        """Buscar un score especifico."""
        repo = InMemoryHoleScoreRepository()
        match_id = MatchId.generate()
        player = UserId.generate()
        hs = _make_hole_score(match_id=match_id, hole_number=5, player_user_id=player)
        await repo.add(hs)

        found = await repo.find_one(match_id, 5, player)
        assert found is not None
        assert found == hs

    async def test_find_one_not_found(self):
        """Retorna None si no existe."""
        repo = InMemoryHoleScoreRepository()
        found = await repo.find_one(MatchId.generate(), 1, UserId.generate())
        assert found is None

    async def test_find_by_match_and_player(self):
        """Buscar todos los scores de un jugador en un match."""
        repo = InMemoryHoleScoreRepository()
        match_id = MatchId.generate()
        player = UserId.generate()
        for h in range(1, 19):
            await repo.add(_make_hole_score(match_id=match_id, hole_number=h, player_user_id=player))
        # Add another player's score
        await repo.add(_make_hole_score(match_id=match_id, hole_number=1, player_user_id=UserId.generate(), team="B"))

        found = await repo.find_by_match_and_player(match_id, player)
        assert len(found) == 18

    async def test_find_by_match_empty(self):
        """Retorna lista vacia si no hay scores."""
        repo = InMemoryHoleScoreRepository()
        found = await repo.find_by_match(MatchId.generate())
        assert found == []


class TestInMemoryHoleScoreRepositoryUpdate:
    """Tests para update()."""

    async def test_update_score(self):
        """Actualizar un score existente."""
        repo = InMemoryHoleScoreRepository()
        match_id = MatchId.generate()
        player = UserId.generate()
        hs = _make_hole_score(match_id=match_id, hole_number=1, player_user_id=player)
        await repo.add(hs)

        hs.set_own_score(5)
        await repo.update(hs)

        found = await repo.find_one(match_id, 1, player)
        assert found.own_score == 5
        assert found.own_submitted is True


class TestInMemoryHoleScoreRepositoryDelete:
    """Tests para delete_by_match()."""

    async def test_delete_by_match(self):
        """Eliminar todos los scores de un match."""
        repo = InMemoryHoleScoreRepository()
        match_id = MatchId.generate()
        for h in range(1, 4):
            await repo.add(_make_hole_score(match_id=match_id, hole_number=h))
        # Another match
        other_match = MatchId.generate()
        await repo.add(_make_hole_score(match_id=other_match, hole_number=1))

        count = await repo.delete_by_match(match_id)
        assert count == 3
        assert await repo.find_by_match(match_id) == []
        assert len(await repo.find_by_match(other_match)) == 1

    async def test_delete_by_match_empty(self):
        """Delete de match sin scores retorna 0."""
        repo = InMemoryHoleScoreRepository()
        count = await repo.delete_by_match(MatchId.generate())
        assert count == 0
