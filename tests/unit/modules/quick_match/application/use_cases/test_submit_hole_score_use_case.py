"""Tests para SubmitQuickMatchHoleScoreUseCase."""

from uuid import uuid4

import pytest

from src.modules.competition.domain.value_objects.match_format import MatchFormat
from src.modules.golf_course.domain.value_objects.golf_course_id import GolfCourseId
from src.modules.quick_match.application.dto.quick_match_dto import SubmitHoleScoreRequestDTO
from src.modules.quick_match.application.exceptions import (
    NotAScorerError,
    NotQuickMatchParticipantError,
    QuickMatchNotFoundError,
)
from src.modules.quick_match.application.use_cases.submit_hole_score_use_case import (
    SubmitQuickMatchHoleScoreUseCase,
)
from src.modules.quick_match.domain.entities.quick_match import QuickMatch
from src.modules.quick_match.domain.exceptions.quick_match_violations import (
    InvalidHoleScoreViolation,
    InvalidQuickMatchStatusViolation,
)
from src.modules.quick_match.domain.value_objects.quick_match_id import QuickMatchId
from src.modules.quick_match.domain.value_objects.quick_match_participant import (
    QuickMatchParticipant,
)
from src.modules.quick_match.domain.value_objects.scoring_format import ScoringFormat
from src.modules.user.domain.value_objects.user_id import UserId
from tests.unit.modules.quick_match.conftest import create_user

pytestmark = pytest.mark.asyncio


async def _create_in_progress_match(qm_uow, creator_id, other_id, scorer_ids=None):
    qm = QuickMatch.create(
        id=QuickMatchId.generate(),
        creator_id=creator_id,
        golf_course_id=GolfCourseId(uuid4()),
        match_format=MatchFormat.SINGLES,
    )
    qm.add_participant(QuickMatchParticipant.for_user(other_id))
    qm.start(scorer_ids or [qm.creator_participant_id])
    async with qm_uow:
        await qm_uow.quick_matches.add(qm)
    return qm


class TestSubmitQuickMatchHoleScoreUseCase:
    async def test_submit_new_score_succeeds(self, qm_uow, user_uow):
        creator = await create_user(user_uow, "creator@test.com")
        other = await create_user(user_uow, "other@test.com")
        qm = await _create_in_progress_match(qm_uow, creator.id, other.id)

        use_case = SubmitQuickMatchHoleScoreUseCase(qm_uow)
        response = await use_case.execute(
            SubmitHoleScoreRequestDTO(
                quick_match_id=qm.id.value,
                player_user_id=creator.id.value,
                hole_number=1,
                score=4,
            )
        )

        assert response.score == 4
        assert response.recorded_by_participant_id == creator.id.value

    async def test_resubmit_updates_existing_score(self, qm_uow, user_uow):
        creator = await create_user(user_uow, "creator2@test.com")
        other = await create_user(user_uow, "other2@test.com")
        qm = await _create_in_progress_match(qm_uow, creator.id, other.id)

        use_case = SubmitQuickMatchHoleScoreUseCase(qm_uow)
        dto = SubmitHoleScoreRequestDTO(
            quick_match_id=qm.id.value,
            player_user_id=creator.id.value,
            hole_number=1,
            score=4,
        )
        await use_case.execute(dto)
        dto2 = dto.model_copy(update={"score": 5})
        response = await use_case.execute(dto2)

        assert response.score == 5
        async with qm_uow:
            scores = await qm_uow.quick_match_hole_scores.find_by_match(qm.id)
        assert len(scores) == 1

    async def test_non_participant_cannot_submit(self, qm_uow, user_uow):
        creator = await create_user(user_uow, "creator3@test.com")
        other = await create_user(user_uow, "other3@test.com")
        qm = await _create_in_progress_match(qm_uow, creator.id, other.id)

        use_case = SubmitQuickMatchHoleScoreUseCase(qm_uow)
        with pytest.raises(NotQuickMatchParticipantError):
            await use_case.execute(
                SubmitHoleScoreRequestDTO(
                    quick_match_id=qm.id.value,
                    player_user_id=UserId(uuid4()).value,
                    hole_number=1,
                    score=4,
                )
            )

    async def test_non_scorer_participant_cannot_self_submit(self, qm_uow, user_uow):
        creator = await create_user(user_uow, "creator5@test.com")
        other = await create_user(user_uow, "other5@test.com")
        # Solo el creador es anotador; `other` es participante pero no anotador.
        qm = await _create_in_progress_match(
            qm_uow, creator.id, other.id, scorer_ids=None
        )

        use_case = SubmitQuickMatchHoleScoreUseCase(qm_uow)
        with pytest.raises(NotAScorerError):
            await use_case.execute(
                SubmitHoleScoreRequestDTO(
                    quick_match_id=qm.id.value,
                    player_user_id=other.id.value,
                    hole_number=1,
                    score=4,
                )
            )

    async def test_cannot_submit_before_starting(self, qm_uow, user_uow):
        creator = await create_user(user_uow, "creator4@test.com")
        qm = QuickMatch.create(
            id=QuickMatchId.generate(),
            creator_id=creator.id,
            golf_course_id=GolfCourseId(uuid4()),
            match_format=MatchFormat.SINGLES,
        )
        async with qm_uow:
            await qm_uow.quick_matches.add(qm)

        use_case = SubmitQuickMatchHoleScoreUseCase(qm_uow)
        with pytest.raises(InvalidQuickMatchStatusViolation):
            await use_case.execute(
                SubmitHoleScoreRequestDTO(
                    quick_match_id=qm.id.value,
                    player_user_id=creator.id.value,
                    hole_number=1,
                    score=4,
                )
            )

    async def test_not_found_raises(self, qm_uow, user_uow):
        use_case = SubmitQuickMatchHoleScoreUseCase(qm_uow)
        with pytest.raises(QuickMatchNotFoundError):
            await use_case.execute(
                SubmitHoleScoreRequestDTO(
                    quick_match_id=uuid4(),
                    player_user_id=uuid4(),
                    hole_number=1,
                    score=4,
                )
            )


class TestSubmitQuickMatchHoleScorePickedUp:
    """La raya: hoyo anotado sin numero porque el jugador recogio la bola."""

    async def test_submit_raya_succeeds(self, qm_uow, user_uow):
        """
        Given un jugador que recoge la bola en un hoyo
        When lo anota con score nulo
        Then queda registrado como raya, no rechazado

        Es el defecto que trajo esto: el frontend mandaba `score: null` y el
        endpoint lo tumbaba con un 422, que la pantalla traducia a "Ese
        resultado no es valido".
        """
        creator = await create_user(user_uow, "raya-creator@test.com")
        other = await create_user(user_uow, "raya-other@test.com")
        qm = await _create_in_progress_match(qm_uow, creator.id, other.id)

        use_case = SubmitQuickMatchHoleScoreUseCase(qm_uow)
        response = await use_case.execute(
            SubmitHoleScoreRequestDTO(
                quick_match_id=qm.id.value,
                player_user_id=creator.id.value,
                hole_number=1,
                score=None,
            )
        )

        assert response.score is None
        assert response.recorded_by_participant_id == creator.id.value

    async def test_a_scored_hole_can_be_corrected_to_a_raya(self, qm_uow, user_uow):
        """
        Given un hoyo ya anotado con golpes
        When se rectifica a raya
        Then el score guardado queda nulo, sin crear una fila nueva
        """
        creator = await create_user(user_uow, "raya-fix@test.com")
        other = await create_user(user_uow, "raya-fix2@test.com")
        qm = await _create_in_progress_match(qm_uow, creator.id, other.id)

        use_case = SubmitQuickMatchHoleScoreUseCase(qm_uow)
        dto = SubmitHoleScoreRequestDTO(
            quick_match_id=qm.id.value,
            player_user_id=creator.id.value,
            hole_number=1,
            score=6,
        )
        await use_case.execute(dto)
        response = await use_case.execute(dto.model_copy(update={"score": None}))

        assert response.score is None
        async with qm_uow:
            stored = await qm_uow.quick_match_hole_scores.find_by_match(qm.id)
        assert len(stored) == 1
        assert stored[0].score is None


class TestMedalRejectsPickedUpHoles:
    """En Medal se emboca en todos los hoyos: la raya no es anotable."""

    async def _create_medal_match(self, qm_uow, creator_id, other_id):
        qm = QuickMatch.create(
            id=QuickMatchId.generate(),
            creator_id=creator_id,
            golf_course_id=GolfCourseId(uuid4()),
            scoring_format=ScoringFormat.MEDAL,
        )
        qm.add_participant(QuickMatchParticipant.for_user(other_id))
        qm.start([qm.creator_participant_id])
        async with qm_uow:
            await qm_uow.quick_matches.add(qm)
        return qm

    async def test_a_raya_is_rejected_in_medal(self, qm_uow, user_uow):
        """
        Given una partida libre en Medal
        When alguien intenta anotar un hoyo con score nulo
        Then se rechaza, porque en stroke play no vale recoger
        """
        creator = await create_user(user_uow, "medal-raya@test.com")
        other = await create_user(user_uow, "medal-raya2@test.com")
        qm = await self._create_medal_match(qm_uow, creator.id, other.id)

        use_case = SubmitQuickMatchHoleScoreUseCase(qm_uow)
        with pytest.raises(InvalidHoleScoreViolation):
            await use_case.execute(
                SubmitHoleScoreRequestDTO(
                    quick_match_id=qm.id.value,
                    player_user_id=creator.id.value,
                    hole_number=1,
                    score=None,
                )
            )

    async def test_a_number_is_still_accepted_in_medal(self, qm_uow, user_uow):
        """El rechazo es de la raya, no de anotar en Medal."""
        creator = await create_user(user_uow, "medal-ok@test.com")
        other = await create_user(user_uow, "medal-ok2@test.com")
        qm = await self._create_medal_match(qm_uow, creator.id, other.id)

        use_case = SubmitQuickMatchHoleScoreUseCase(qm_uow)
        response = await use_case.execute(
            SubmitHoleScoreRequestDTO(
                quick_match_id=qm.id.value,
                player_user_id=creator.id.value,
                hole_number=1,
                score=5,
            )
        )

        assert response.score == 5
