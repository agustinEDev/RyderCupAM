"""Tests para SubmitHoleScoreUseCase."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.modules.competition.application.dto.scoring_dto import SubmitHoleScoreBodyDTO
from src.modules.competition.application.exceptions import (
    InvalidHoleNumberError,
    MatchNotFoundError,
    MatchNotScoringError,
    NotMatchPlayerError,
)
from src.modules.competition.application.use_cases.submit_hole_score_use_case import (
    SubmitHoleScoreUseCase,
)
from src.modules.competition.domain.entities.hole_score import HoleScore
from src.modules.competition.domain.entities.match import Match
from src.modules.competition.domain.services.scoring_service import ScoringService
from src.modules.competition.domain.value_objects.marker_assignment import MarkerAssignment
from src.modules.competition.domain.value_objects.match_format import MatchFormat
from src.modules.competition.domain.value_objects.match_player import MatchPlayer
from src.modules.competition.domain.value_objects.match_status import MatchStatus
from src.modules.competition.domain.value_objects.round_id import RoundId
from src.modules.competition.infrastructure.persistence.in_memory.in_memory_unit_of_work import (
    InMemoryUnitOfWork,
)
from src.modules.golf_course.domain.value_objects.tee_category import TeeCategory
from src.modules.user.domain.value_objects.user_id import UserId


def _make_player(user_id=None, handicap=10, strokes=()):
    return MatchPlayer.create(
        user_id=user_id or UserId.generate(),
        playing_handicap=handicap,
        tee_category=TeeCategory.AMATEUR,
        strokes_received=list(strokes),
    )


def _setup_match(uow, team_a, team_b, status=MatchStatus.IN_PROGRESS, match_format=MatchFormat.SINGLES, marker_assignments=None):
    """Creates a match and round in the UoW."""
    round_id = RoundId.generate()

    # Create a mock round
    mock_round = MagicMock()
    mock_round.id = round_id
    mock_round.match_format = match_format
    mock_round.competition_id = MagicMock()
    mock_round.round_date = None
    mock_round.session_type = MagicMock(value="MORNING")

    match = Match.create(
        round_id=round_id,
        match_number=1,
        team_a_players=team_a,
        team_b_players=team_b,
    )
    if marker_assignments:
        match.set_marker_assignments(marker_assignments)
    if status == MatchStatus.IN_PROGRESS:
        match.start()
    return match, mock_round


@pytest.fixture
def uow():
    return InMemoryUnitOfWork()


@pytest.fixture
def scoring_service():
    return ScoringService()


@pytest.fixture
def user_repo():
    def _make_mock_user(uid):
        user = MagicMock()
        user.first_name = "Player"
        user.last_name = str(uid)[:8]
        return user

    repo = AsyncMock()
    repo.find_by_id = AsyncMock(side_effect=_make_mock_user)
    return repo


class TestSubmitHoleScoreValidation:
    @pytest.mark.asyncio
    async def test_match_not_found(self, uow, user_repo, scoring_service):
        uc = SubmitHoleScoreUseCase(uow, user_repo, scoring_service)
        body = SubmitHoleScoreBodyDTO(own_score=5, marked_player_id=str(UserId.generate()), marked_score=4)
        with pytest.raises(MatchNotFoundError):
            await uc.execute(str(UserId.generate()), 1, body, UserId.generate())

    @pytest.mark.asyncio
    async def test_match_not_in_progress(self, uow, user_repo, scoring_service):
        a, b = _make_player(), _make_player()
        match, _mock_round = _setup_match(uow, [a], [b], status=MatchStatus.SCHEDULED)
        await uow.matches.add(match)
        uc = SubmitHoleScoreUseCase(uow, user_repo, scoring_service)
        body = SubmitHoleScoreBodyDTO(own_score=5, marked_player_id=str(b.user_id), marked_score=4)
        with pytest.raises(MatchNotScoringError):
            await uc.execute(str(match.id), 1, body, a.user_id)

    @pytest.mark.asyncio
    async def test_not_match_player(self, uow, user_repo, scoring_service):
        a, b = _make_player(), _make_player()
        match, mock_round = _setup_match(uow, [a], [b])
        await uow.matches.add(match)
        uow._rounds._rounds[mock_round.id] = mock_round

        uc = SubmitHoleScoreUseCase(uow, user_repo, scoring_service)
        body = SubmitHoleScoreBodyDTO(own_score=5, marked_player_id=str(b.user_id), marked_score=4)
        with pytest.raises(NotMatchPlayerError):
            await uc.execute(str(match.id), 1, body, UserId.generate())

    @pytest.mark.asyncio
    async def test_scorecard_submitted_skips_own_score_allows_marker(self, uow, user_repo, scoring_service):
        """Tras entregar tarjeta, own_score se ignora silenciosamente y marker_score se procesa."""
        a, b = _make_player(), _make_player()
        assignments = [
            MarkerAssignment(scorer_user_id=a.user_id, marks_user_id=b.user_id, marked_by_user_id=b.user_id),
            MarkerAssignment(scorer_user_id=b.user_id, marks_user_id=a.user_id, marked_by_user_id=a.user_id),
        ]
        match, mock_round = _setup_match(uow, [a], [b], marker_assignments=assignments)
        await uow.matches.add(match)
        uow._rounds._rounds[mock_round.id] = mock_round

        # Pre-create hole scores con own_score existente
        hs_a = HoleScore.create(match_id=match.id, hole_number=1, player_user_id=a.user_id, team="A", strokes_received=0)
        hs_b = HoleScore.create(match_id=match.id, hole_number=1, player_user_id=b.user_id, team="B", strokes_received=0)
        hs_a.set_own_score(4)
        await uow.hole_scores.add(hs_a)
        await uow.hole_scores.add(hs_b)

        # Entregar tarjeta de A
        match.submit_scorecard(a.user_id)
        await uow.matches.update(match)

        # Mock competition for scoring view
        mock_comp = MagicMock()
        mock_comp.id = mock_round.competition_id
        mock_comp.team_1_name = "Team A"
        mock_comp.team_2_name = "Team B"
        uow._competitions._competitions[mock_comp.id] = mock_comp

        uc = SubmitHoleScoreUseCase(uow, user_repo, scoring_service)
        # Frontend envia own_score=5 pero debe ignorarse, marker_score=4 debe procesarse
        body = SubmitHoleScoreBodyDTO(own_score=5, marked_player_id=str(b.user_id), marked_score=4)
        result = await uc.execute(str(match.id), 1, body, a.user_id)

        assert result.match_id == str(match.id)
        # own_score de A no cambió (sigue en 4, no se actualizó a 5)
        updated_a = await uow.hole_scores.find_one(match.id, 1, a.user_id)
        assert updated_a.own_score == 4
        # marker_score de B si se actualizó
        updated_b = await uow.hole_scores.find_one(match.id, 1, b.user_id)
        assert updated_b.marker_score == 4

    @pytest.mark.asyncio
    async def test_marked_player_scorecard_submitted_skips_marker_allows_own(self, uow, user_repo, scoring_service):
        """Si el jugador que marcas ya entregó tarjeta, marker_score se ignora y own_score se procesa."""
        a, b = _make_player(), _make_player()
        assignments = [
            MarkerAssignment(scorer_user_id=a.user_id, marks_user_id=b.user_id, marked_by_user_id=b.user_id),
            MarkerAssignment(scorer_user_id=b.user_id, marks_user_id=a.user_id, marked_by_user_id=a.user_id),
        ]
        match, mock_round = _setup_match(uow, [a], [b], marker_assignments=assignments)
        await uow.matches.add(match)
        uow._rounds._rounds[mock_round.id] = mock_round

        # Pre-create hole scores con marker_score existente en B
        hs_a = HoleScore.create(match_id=match.id, hole_number=1, player_user_id=a.user_id, team="A", strokes_received=0)
        hs_b = HoleScore.create(match_id=match.id, hole_number=1, player_user_id=b.user_id, team="B", strokes_received=0)
        hs_b.set_marker_score(3)
        await uow.hole_scores.add(hs_a)
        await uow.hole_scores.add(hs_b)

        # B entrega tarjeta
        match.submit_scorecard(b.user_id)
        await uow.matches.update(match)

        # Mock competition for scoring view
        mock_comp = MagicMock()
        mock_comp.id = mock_round.competition_id
        mock_comp.team_1_name = "Team A"
        mock_comp.team_2_name = "Team B"
        uow._competitions._competitions[mock_comp.id] = mock_comp

        uc = SubmitHoleScoreUseCase(uow, user_repo, scoring_service)
        body = SubmitHoleScoreBodyDTO(own_score=5, marked_player_id=str(b.user_id), marked_score=7)
        result = await uc.execute(str(match.id), 1, body, a.user_id)

        assert result.match_id == str(match.id)
        # own_score de A si se actualizó
        updated_a = await uow.hole_scores.find_one(match.id, 1, a.user_id)
        assert updated_a.own_score == 5
        # marker_score de B no cambió (sigue en 3, no se actualizó a 7)
        updated_b = await uow.hole_scores.find_one(match.id, 1, b.user_id)
        assert updated_b.marker_score == 3

    @pytest.mark.asyncio
    async def test_invalid_hole_number(self, uow, user_repo, scoring_service):
        a, b = _make_player(), _make_player()
        match, mock_round = _setup_match(uow, [a], [b])
        await uow.matches.add(match)
        uow._rounds._rounds[mock_round.id] = mock_round

        uc = SubmitHoleScoreUseCase(uow, user_repo, scoring_service)
        body = SubmitHoleScoreBodyDTO(own_score=5, marked_player_id=str(b.user_id), marked_score=4)
        with pytest.raises(InvalidHoleNumberError):
            await uc.execute(str(match.id), 19, body, a.user_id)


class TestSubmitHoleScoreHappyPath:
    @pytest.mark.asyncio
    async def test_updates_own_and_marker_scores(self, uow, user_repo, scoring_service):
        a, b = _make_player(), _make_player()
        assignments = [
            MarkerAssignment(scorer_user_id=a.user_id, marks_user_id=b.user_id, marked_by_user_id=b.user_id),
            MarkerAssignment(scorer_user_id=b.user_id, marks_user_id=a.user_id, marked_by_user_id=a.user_id),
        ]
        match, mock_round = _setup_match(uow, [a], [b], marker_assignments=assignments)
        await uow.matches.add(match)
        uow._rounds._rounds[mock_round.id] = mock_round

        # Pre-create hole scores
        hs_a = HoleScore.create(match_id=match.id, hole_number=1, player_user_id=a.user_id, team="A", strokes_received=0)
        hs_b = HoleScore.create(match_id=match.id, hole_number=1, player_user_id=b.user_id, team="B", strokes_received=0)
        await uow.hole_scores.add(hs_a)
        await uow.hole_scores.add(hs_b)

        # Mock competition for scoring view
        mock_comp = MagicMock()
        mock_comp.id = mock_round.competition_id
        mock_comp.team_1_name = "Team A"
        mock_comp.team_2_name = "Team B"
        uow._competitions._competitions[mock_comp.id] = mock_comp

        uc = SubmitHoleScoreUseCase(uow, user_repo, scoring_service)
        body = SubmitHoleScoreBodyDTO(own_score=5, marked_player_id=str(b.user_id), marked_score=4)
        result = await uc.execute(str(match.id), 1, body, a.user_id)

        assert result.match_id == str(match.id)

        # Verify own_score was set on player A's HoleScore
        updated_a = await uow.hole_scores.find_one(match.id, 1, a.user_id)
        assert updated_a.own_score == 5
        assert updated_a.own_submitted is True

        # Verify marker_score was set on player B's HoleScore
        updated_b = await uow.hole_scores.find_one(match.id, 1, b.user_id)
        assert updated_b.marker_score == 4
        assert updated_b.marker_submitted is True
