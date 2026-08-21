"""Tests para ExcludeQuickMatchFromStatsUseCase e IncludeQuickMatchInStatsUseCase."""

from uuid import uuid4

import pytest

from src.modules.competition.domain.value_objects.match_format import MatchFormat
from src.modules.golf_course.domain.value_objects.golf_course_id import GolfCourseId
from src.modules.quick_match.application.dto.quick_match_dto import HideQuickMatchRequestDTO
from src.modules.quick_match.application.exceptions import QuickMatchNotFoundError
from src.modules.quick_match.application.use_cases.exclude_quick_match_from_stats_use_case import (
    ExcludeQuickMatchFromStatsUseCase,
)
from src.modules.quick_match.application.use_cases.include_quick_match_in_stats_use_case import (
    IncludeQuickMatchInStatsUseCase,
)
from src.modules.quick_match.domain.entities.quick_match import QuickMatch
from src.modules.quick_match.domain.exceptions.quick_match_violations import (
    InvalidQuickMatchStatusViolation,
    NotQuickMatchParticipantViolation,
)
from src.modules.quick_match.domain.value_objects.quick_match_id import QuickMatchId
from src.modules.quick_match.domain.value_objects.quick_match_participant import (
    QuickMatchParticipant,
)
from src.modules.user.domain.value_objects.user_id import UserId

pytestmark = pytest.mark.asyncio


async def _create_completed_match(qm_uow, creator_id):
    """Partida terminada con dos jugadores registrados."""
    qm = QuickMatch.create(
        id=QuickMatchId.generate(),
        creator_id=creator_id,
        golf_course_id=GolfCourseId(uuid4()),
        match_format=MatchFormat.SINGLES,
    )
    other = QuickMatchParticipant.for_user(UserId(uuid4()))
    qm.add_participant(other)
    qm.start([qm.creator_participant_id])
    qm.complete()
    async with qm_uow:
        await qm_uow.quick_matches.add(qm)
    return qm, other


async def _create_in_progress_match(qm_uow, creator_id):
    qm = QuickMatch.create(
        id=QuickMatchId.generate(),
        creator_id=creator_id,
        golf_course_id=GolfCourseId(uuid4()),
        match_format=MatchFormat.SINGLES,
    )
    qm.add_participant(QuickMatchParticipant.for_user(UserId(uuid4())))
    qm.start([qm.creator_participant_id])
    async with qm_uow:
        await qm_uow.quick_matches.add(qm)
    return qm


class TestExcludeQuickMatchFromStatsUseCase:
    async def test_creator_can_exclude_a_completed_match(self, qm_uow, user_uow):
        creator = UserId(uuid4())
        qm, _other = await _create_completed_match(qm_uow, creator)

        use_case = ExcludeQuickMatchFromStatsUseCase(qm_uow, user_uow)
        await use_case.execute(
            HideQuickMatchRequestDTO(quick_match_id=qm.id.value, requester_id=creator.value)
        )

        stored = await qm_uow.quick_matches.find_by_id(qm.id)
        assert stored.is_stats_excluded_for(qm.creator_participant_id)

    async def test_excluding_does_not_hide_the_match(self, qm_uow, user_uow):
        """Lo que separa esta marca de ocultar: la partida sigue en el historial."""
        creator = UserId(uuid4())
        qm, _other = await _create_completed_match(qm_uow, creator)

        use_case = ExcludeQuickMatchFromStatsUseCase(qm_uow, user_uow)
        await use_case.execute(
            HideQuickMatchRequestDTO(quick_match_id=qm.id.value, requester_id=creator.value)
        )

        stored = await qm_uow.quick_matches.find_by_id(qm.id)
        assert not stored.is_hidden_for(qm.creator_participant_id)
        listed = await qm_uow.quick_matches.list_for_user(creator)
        assert [m.id for m in listed] == [qm.id]

    async def test_any_participant_can_exclude_for_themselves(self, qm_uow, user_uow):
        creator = UserId(uuid4())
        qm, other = await _create_completed_match(qm_uow, creator)

        use_case = ExcludeQuickMatchFromStatsUseCase(qm_uow, user_uow)
        await use_case.execute(
            HideQuickMatchRequestDTO(quick_match_id=qm.id.value, requester_id=other.user_id.value)
        )

        stored = await qm_uow.quick_matches.find_by_id(qm.id)
        assert stored.is_stats_excluded_for(other.participant_id)
        assert not stored.is_stats_excluded_for(qm.creator_participant_id)

    async def test_response_reports_the_flag_for_the_caller_only(self, qm_uow, user_uow):
        """`excluded_from_stats` responde a QUIEN pregunta, no al estado global."""
        creator = UserId(uuid4())
        qm, other = await _create_completed_match(qm_uow, creator)

        exclude = ExcludeQuickMatchFromStatsUseCase(qm_uow, user_uow)
        response = await exclude.execute(
            HideQuickMatchRequestDTO(quick_match_id=qm.id.value, requester_id=other.user_id.value)
        )

        assert response.excluded_from_stats is True

    async def test_excluding_a_match_in_progress_raises(self, qm_uow, user_uow):
        creator = UserId(uuid4())
        qm = await _create_in_progress_match(qm_uow, creator)

        use_case = ExcludeQuickMatchFromStatsUseCase(qm_uow, user_uow)
        with pytest.raises(InvalidQuickMatchStatusViolation):
            await use_case.execute(
                HideQuickMatchRequestDTO(quick_match_id=qm.id.value, requester_id=creator.value)
            )

    async def test_non_participant_raises(self, qm_uow, user_uow):
        """
        Un extraño no puede tocar una partida ajena. Se distingue de "no existe"
        en el dominio; la ruta traduce las dos a 404 para no confirmar que la
        partida existe a quien no tiene nada que ver con ella.
        """
        creator = UserId(uuid4())
        qm, _other = await _create_completed_match(qm_uow, creator)

        use_case = ExcludeQuickMatchFromStatsUseCase(qm_uow, user_uow)
        with pytest.raises(NotQuickMatchParticipantViolation):
            await use_case.execute(
                HideQuickMatchRequestDTO(quick_match_id=qm.id.value, requester_id=uuid4())
            )

    async def test_not_found_raises(self, qm_uow, user_uow):
        use_case = ExcludeQuickMatchFromStatsUseCase(qm_uow, user_uow)
        with pytest.raises(QuickMatchNotFoundError):
            await use_case.execute(
                HideQuickMatchRequestDTO(quick_match_id=uuid4(), requester_id=uuid4())
            )


class TestIncludeQuickMatchInStatsUseCase:
    async def test_reverses_a_previous_exclusion(self, qm_uow, user_uow):
        creator = UserId(uuid4())
        qm, _other = await _create_completed_match(qm_uow, creator)
        qm.exclude_from_stats_for(qm.creator_participant_id)
        async with qm_uow:
            await qm_uow.quick_matches.update(qm)

        use_case = IncludeQuickMatchInStatsUseCase(qm_uow, user_uow)
        response = await use_case.execute(
            HideQuickMatchRequestDTO(quick_match_id=qm.id.value, requester_id=creator.value)
        )

        stored = await qm_uow.quick_matches.find_by_id(qm.id)
        assert not stored.is_stats_excluded_for(qm.creator_participant_id)
        assert response.excluded_from_stats is False

    async def test_is_idempotent(self, qm_uow, user_uow):
        creator = UserId(uuid4())
        qm, _other = await _create_completed_match(qm_uow, creator)

        use_case = IncludeQuickMatchInStatsUseCase(qm_uow, user_uow)
        await use_case.execute(
            HideQuickMatchRequestDTO(quick_match_id=qm.id.value, requester_id=creator.value)
        )

        stored = await qm_uow.quick_matches.find_by_id(qm.id)
        assert not stored.is_stats_excluded_for(qm.creator_participant_id)

    async def test_non_participant_raises(self, qm_uow, user_uow):
        creator = UserId(uuid4())
        qm, _other = await _create_completed_match(qm_uow, creator)

        use_case = IncludeQuickMatchInStatsUseCase(qm_uow, user_uow)
        with pytest.raises(NotQuickMatchParticipantViolation):
            await use_case.execute(
                HideQuickMatchRequestDTO(quick_match_id=qm.id.value, requester_id=uuid4())
            )
