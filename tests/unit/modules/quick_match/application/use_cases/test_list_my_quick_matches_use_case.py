"""Tests para ListMyQuickMatchesUseCase."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from src.modules.golf_course.domain.value_objects.golf_course_id import GolfCourseId
from src.modules.quick_match.application.use_cases.list_my_quick_matches_use_case import (
    ListMyQuickMatchesUseCase,
)
from src.modules.quick_match.domain.entities.quick_match import QuickMatch
from src.modules.quick_match.domain.value_objects.quick_match_id import QuickMatchId
from src.shared.domain.value_objects.match_format import MatchFormat
from tests.unit.modules.quick_match.conftest import create_user

pytestmark = pytest.mark.asyncio


class TestListMyQuickMatchesUseCase:
    async def test_lists_only_matches_where_user_participates(self, qm_uow, user_uow):
        me = await create_user(user_uow, "me@test.com")
        other = await create_user(user_uow, "other@test.com")

        mine = QuickMatch.create(
            id=QuickMatchId.generate(),
            creator_id=me.id,
            golf_course_id=GolfCourseId(uuid4()),
            match_format=MatchFormat.SINGLES,
        )
        not_mine = QuickMatch.create(
            id=QuickMatchId.generate(),
            creator_id=other.id,
            golf_course_id=GolfCourseId(uuid4()),
            match_format=MatchFormat.SINGLES,
        )
        async with qm_uow:
            await qm_uow.quick_matches.add(mine)
            await qm_uow.quick_matches.add(not_mine)

        use_case = ListMyQuickMatchesUseCase(qm_uow, user_uow)
        result = await use_case.execute(str(me.id.value))

        assert result.total_count == 1
        assert result.quick_matches[0].id == mine.id.value

    async def test_excludes_matches_the_user_has_hidden(self, qm_uow, user_uow):
        """Ver RyderCupAm#127: ocultar una partida la saca del listado propio (no un borrado)."""
        me = await create_user(user_uow, "me-hides@test.com")

        visible = QuickMatch.create(
            id=QuickMatchId.generate(),
            creator_id=me.id,
            golf_course_id=GolfCourseId(uuid4()),
            match_format=MatchFormat.SINGLES,
        )
        hidden = QuickMatch.create(
            id=QuickMatchId.generate(),
            creator_id=me.id,
            golf_course_id=GolfCourseId(uuid4()),
            match_format=MatchFormat.SINGLES,
        )
        hidden.hide_for(hidden.creator_participant_id)
        async with qm_uow:
            await qm_uow.quick_matches.add(visible)
            await qm_uow.quick_matches.add(hidden)

        use_case = ListMyQuickMatchesUseCase(qm_uow, user_uow)
        result = await use_case.execute(str(me.id.value))

        assert result.total_count == 1
        assert result.quick_matches[0].id == visible.id.value

    async def test_h5_each_match_says_when_it_was_played(self, qm_uow, user_uow):
        """
        H5 (25 oct 2026): «Mis partidas rápidas» enseñaba la fecha de creación.
        `played_at` es cuando empezó (o cuando se creó si nunca empezó), en UTC
        con su zona.
        """
        me = await create_user(user_uow, "me-played@test.com")
        started = QuickMatch.create(
            id=QuickMatchId.generate(),
            creator_id=me.id,
            golf_course_id=GolfCourseId(uuid4()),
            match_format=MatchFormat.SINGLES,
        )
        started._created_at = datetime(2026, 10, 15, 18, 0)
        started._started_at = datetime(2026, 10, 21, 22, 30)
        pending = QuickMatch.create(
            id=QuickMatchId.generate(),
            creator_id=me.id,
            golf_course_id=GolfCourseId(uuid4()),
            match_format=MatchFormat.SINGLES,
        )
        pending._created_at = datetime(2026, 10, 20, 9, 0)
        async with qm_uow:
            await qm_uow.quick_matches.add(started)
            await qm_uow.quick_matches.add(pending)

        result = await ListMyQuickMatchesUseCase(qm_uow, user_uow).execute(str(me.id.value))

        por_id = {m.id: m for m in result.quick_matches}
        assert por_id[started.id.value].played_at == datetime(2026, 10, 21, 22, 30, tzinfo=UTC)
        assert por_id[pending.id.value].played_at == datetime(2026, 10, 20, 9, 0, tzinfo=UTC)
        assert por_id[started.id.value].played_at.tzinfo is not None
