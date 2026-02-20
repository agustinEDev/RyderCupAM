"""Tests para SubmitScorecardUseCase."""

from unittest.mock import MagicMock

import pytest

from src.modules.competition.application.exceptions import (
    MatchNotFoundError,
    MatchNotScoringError,
    NotMatchPlayerError,
    ScorecardAlreadySubmittedError,
    ScorecardNotReadyError,
)
from src.modules.competition.application.use_cases.submit_scorecard_use_case import (
    SubmitScorecardUseCase,
)
from src.modules.competition.domain.entities.hole_score import HoleScore
from src.modules.competition.domain.entities.match import Match
from src.modules.competition.domain.services.scoring_service import ScoringService
from src.modules.competition.domain.value_objects.match_format import MatchFormat
from src.modules.competition.domain.value_objects.match_player import MatchPlayer
from src.modules.competition.domain.value_objects.round_id import RoundId
from src.modules.competition.domain.value_objects.round_status import RoundStatus
from src.modules.competition.infrastructure.persistence.in_memory.in_memory_unit_of_work import (
    InMemoryUnitOfWork,
)
from src.modules.golf_course.domain.value_objects.tee_category import TeeCategory
from src.modules.user.domain.value_objects.user_id import UserId


def _make_player(user_id=None):
    return MatchPlayer.create(
        user_id=user_id or UserId.generate(),
        playing_handicap=10,
        tee_category=TeeCategory.AMATEUR,
        strokes_received=[],
    )


@pytest.fixture
def uow():
    return InMemoryUnitOfWork()


@pytest.fixture
def scoring_service():
    return ScoringService()


class TestSubmitScorecardValidation:
    @pytest.mark.asyncio
    async def test_match_not_found(self, uow, scoring_service):
        uc = SubmitScorecardUseCase(uow, scoring_service)
        with pytest.raises(MatchNotFoundError):
            await uc.execute(str(UserId.generate()), UserId.generate())

    @pytest.mark.asyncio
    async def test_match_not_in_progress(self, uow, scoring_service):
        a, b = _make_player(), _make_player()
        match = Match.create(round_id=RoundId.generate(), match_number=1, team_a_players=[a], team_b_players=[b])
        await uow.matches.add(match)
        uc = SubmitScorecardUseCase(uow, scoring_service)
        with pytest.raises(MatchNotScoringError):
            await uc.execute(str(match.id), a.user_id)

    @pytest.mark.asyncio
    async def test_not_match_player(self, uow, scoring_service):
        a, b = _make_player(), _make_player()
        match = Match.create(round_id=RoundId.generate(), match_number=1, team_a_players=[a], team_b_players=[b])
        match.start()
        await uow.matches.add(match)
        uc = SubmitScorecardUseCase(uow, scoring_service)
        with pytest.raises(NotMatchPlayerError):
            await uc.execute(str(match.id), UserId.generate())

    @pytest.mark.asyncio
    async def test_scorecard_already_submitted(self, uow, scoring_service):
        a, b = _make_player(), _make_player()
        match = Match.create(round_id=RoundId.generate(), match_number=1, team_a_players=[a], team_b_players=[b])
        match.start()
        match.submit_scorecard(a.user_id)
        await uow.matches.add(match)
        uc = SubmitScorecardUseCase(uow, scoring_service)
        with pytest.raises(ScorecardAlreadySubmittedError):
            await uc.execute(str(match.id), a.user_id)

    @pytest.mark.asyncio
    async def test_unvalidated_holes_raise(self, uow, scoring_service):
        a, b = _make_player(), _make_player()
        match = Match.create(round_id=RoundId.generate(), match_number=1, team_a_players=[a], team_b_players=[b])
        match.start()
        await uow.matches.add(match)

        # Create HoleScore with own_submitted but MISMATCH
        hs = HoleScore.create(match_id=match.id, hole_number=1, player_user_id=a.user_id, team="A", strokes_received=0)
        hs.set_own_score(5)
        hs.set_marker_score(4)
        hs.recalculate_validation()
        await uow.hole_scores.add(hs)

        uc = SubmitScorecardUseCase(uow, scoring_service)
        with pytest.raises(ScorecardNotReadyError):
            await uc.execute(str(match.id), a.user_id)


class TestSubmitScorecardHappyPath:
    @pytest.mark.asyncio
    async def test_submit_scorecard_not_complete(self, uow, scoring_service):
        """Submitting first scorecard doesn't complete match."""
        a, b = _make_player(), _make_player()
        round_id = RoundId.generate()
        match = Match.create(round_id=round_id, match_number=1, team_a_players=[a], team_b_players=[b])
        match.start()
        await uow.matches.add(match)

        uc = SubmitScorecardUseCase(uow, scoring_service)
        result = await uc.execute(str(match.id), a.user_id)
        assert result.match_complete is False
        assert result.submitted_by == str(a.user_id)

    @pytest.mark.asyncio
    async def test_all_submit_completes_match(self, uow, scoring_service):
        """All players submitting completes the match."""
        a, b = _make_player(), _make_player()
        round_id = RoundId.generate()
        mock_round = MagicMock()
        mock_round.id = round_id
        mock_round.match_format = MatchFormat.SINGLES
        mock_round.status = RoundStatus.IN_PROGRESS
        mock_round.competition_id = MagicMock()
        uow._rounds._rounds[mock_round.id] = mock_round

        match = Match.create(round_id=round_id, match_number=1, team_a_players=[a], team_b_players=[b])
        match.start()

        # Create validated hole scores (18 holes each)
        for hole in range(1, 19):
            hs_a = HoleScore.create(match_id=match.id, hole_number=hole, player_user_id=a.user_id, team="A", strokes_received=0)
            hs_a.set_own_score(4)
            hs_a.set_marker_score(4)
            hs_a.recalculate_validation()
            await uow.hole_scores.add(hs_a)

            hs_b = HoleScore.create(match_id=match.id, hole_number=hole, player_user_id=b.user_id, team="B", strokes_received=0)
            hs_b.set_own_score(5)
            hs_b.set_marker_score(5)
            hs_b.recalculate_validation()
            await uow.hole_scores.add(hs_b)

        match.submit_scorecard(a.user_id)
        await uow.matches.add(match)

        uc = SubmitScorecardUseCase(uow, scoring_service)
        result = await uc.execute(str(match.id), b.user_id)
        assert result.match_complete is True
