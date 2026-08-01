"""Tests para SubmitProxyHoleScoreUseCase."""

from uuid import uuid4

import pytest

from src.modules.competition.domain.value_objects.match_format import MatchFormat
from src.modules.golf_course.domain.value_objects.golf_course_id import GolfCourseId
from src.modules.quick_match.application.dto.quick_match_dto import (
    SubmitProxyHoleScoreRequestDTO,
)
from src.modules.quick_match.application.exceptions import (
    NotAScorerError,
    TargetParticipantNotFoundError,
)
from src.modules.quick_match.application.use_cases.submit_proxy_hole_score_use_case import (
    SubmitProxyHoleScoreUseCase,
)
from src.modules.quick_match.domain.entities.quick_match import QuickMatch
from src.modules.quick_match.domain.exceptions.quick_match_violations import (
    NotAssignedScorerViolation,
)
from src.modules.quick_match.domain.services.scoring_coverage_service import (
    ScoringCoverageService,
)
from src.modules.quick_match.domain.value_objects.quick_match_id import QuickMatchId
from src.modules.quick_match.domain.value_objects.quick_match_participant import (
    QuickMatchParticipant,
)
from tests.unit.modules.quick_match.conftest import create_user

pytestmark = pytest.mark.asyncio


async def _create_in_progress_match_with_guest(qm_uow, creator_id):
    qm = QuickMatch.create(
        id=QuickMatchId.generate(),
        creator_id=creator_id,
        golf_course_id=GolfCourseId(uuid4()),
        match_format=MatchFormat.SINGLES,
    )
    guest = QuickMatchParticipant.for_guest(first_name="Guest", last_name="Player")
    qm.add_participant(guest)
    qm.start([qm.creator_participant_id])
    async with qm_uow:
        await qm_uow.quick_matches.add(qm)
    return qm, guest


class TestSubmitProxyHoleScoreUseCase:
    async def test_scorer_can_submit_for_assigned_guest(self, qm_uow, user_uow):
        creator = await create_user(user_uow, "creator@test.com")
        qm, guest = await _create_in_progress_match_with_guest(qm_uow, creator.id)

        use_case = SubmitProxyHoleScoreUseCase(qm_uow, ScoringCoverageService())
        response = await use_case.execute(
            SubmitProxyHoleScoreRequestDTO(
                quick_match_id=qm.id.value,
                scorer_user_id=creator.id.value,
                target_participant_id=guest.participant_id.value,
                hole_number=1,
                score=5,
            )
        )

        assert response.score == 5
        assert response.participant_id == guest.participant_id.value
        assert response.recorded_by_participant_id == creator.id.value

    async def test_non_scorer_cannot_submit_by_proxy(self, qm_uow, user_uow):
        creator = await create_user(user_uow, "creator2@test.com")
        qm, guest = await _create_in_progress_match_with_guest(qm_uow, creator.id)

        use_case = SubmitProxyHoleScoreUseCase(qm_uow, ScoringCoverageService())
        with pytest.raises(NotAScorerError):
            await use_case.execute(
                SubmitProxyHoleScoreRequestDTO(
                    quick_match_id=qm.id.value,
                    scorer_user_id=uuid4(),
                    target_participant_id=guest.participant_id.value,
                    hole_number=1,
                    score=5,
                )
            )

    async def test_target_not_found_raises(self, qm_uow, user_uow):
        creator = await create_user(user_uow, "creator3@test.com")
        qm, _guest = await _create_in_progress_match_with_guest(qm_uow, creator.id)

        use_case = SubmitProxyHoleScoreUseCase(qm_uow, ScoringCoverageService())
        with pytest.raises(TargetParticipantNotFoundError):
            await use_case.execute(
                SubmitProxyHoleScoreRequestDTO(
                    quick_match_id=qm.id.value,
                    scorer_user_id=creator.id.value,
                    target_participant_id=uuid4(),
                    hole_number=1,
                    score=5,
                )
            )

    async def test_scorer_cannot_submit_for_participant_not_assigned_to_them(
        self, qm_uow, user_uow
    ):
        creator = await create_user(user_uow, "creator4@test.com")
        other = await create_user(user_uow, "other4@test.com")
        qm = QuickMatch.create(
            id=QuickMatchId.generate(),
            creator_id=creator.id,
            golf_course_id=GolfCourseId(uuid4()),
            match_format=MatchFormat.FOURBALL,
        )
        scorer_b = QuickMatchParticipant.for_user(other.id, team="A")
        guest_a = QuickMatchParticipant.for_guest(first_name="Guest", last_name="A", team="B")
        guest_b = QuickMatchParticipant.for_guest(first_name="Guest", last_name="B", team="B")
        qm.add_participant(scorer_b)
        qm.add_participant(guest_a)
        qm.add_participant(guest_b)
        qm.start([qm.creator_participant_id, scorer_b.participant_id])
        async with qm_uow:
            await qm_uow.quick_matches.add(qm)

        # Con 2 anotadores y 2 no-anotadores, el reparto es 1 y 1: cada guest
        # queda asignado a un anotador distinto. Forzamos que "other" intente
        # anotar al invitado que NO le corresponde.
        use_case = SubmitProxyHoleScoreUseCase(qm_uow, ScoringCoverageService())
        assignments = use_case._coverage_service.compute_assignments(
            participants=qm.participants,
            scorer_ids=qm.scorer_ids,
            creator_participant_id=qm.creator_participant_id,
        )
        not_assigned_to_other = next(
            g
            for g in (guest_a, guest_b)
            if g.participant_id not in assignments[scorer_b.participant_id]
        )

        with pytest.raises(NotAssignedScorerViolation):
            await use_case.execute(
                SubmitProxyHoleScoreRequestDTO(
                    quick_match_id=qm.id.value,
                    scorer_user_id=other.id.value,
                    target_participant_id=not_assigned_to_other.participant_id.value,
                    hole_number=1,
                    score=5,
                )
            )
