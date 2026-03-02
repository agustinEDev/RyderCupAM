"""Tests para ConcedeMatchUseCase."""

from unittest.mock import MagicMock

import pytest

from src.modules.competition.application.exceptions import (
    MatchNotFoundError,
    MatchNotScoringError,
    NotMatchPlayerError,
)
from src.modules.competition.application.use_cases.concede_match_use_case import (
    ConcedeMatchUseCase,
)
from src.modules.competition.domain.entities.match import Match
from src.modules.competition.domain.services.scoring_service import ScoringService
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


def _setup(uow, a, b, creator_id):
    """Setup match, round, competition in UoW."""
    round_id = RoundId.generate()
    mock_round = MagicMock()
    mock_round.id = round_id
    mock_round.competition_id = MagicMock()
    mock_round.status = RoundStatus.IN_PROGRESS

    mock_comp = MagicMock()
    mock_comp.id = mock_round.competition_id
    mock_comp.is_creator = lambda uid: uid == creator_id

    match = Match.create(round_id=round_id, match_number=1, team_a_players=[a], team_b_players=[b])
    match.start()
    return match, mock_round, mock_comp


@pytest.fixture
def uow():
    return InMemoryUnitOfWork()


@pytest.fixture
def scoring_service():
    return ScoringService()


class TestConcedeMatchValidation:
    @pytest.mark.asyncio
    async def test_match_not_found(self, uow, scoring_service):
        uc = ConcedeMatchUseCase(uow, scoring_service)
        with pytest.raises(MatchNotFoundError):
            await uc.execute(str(UserId.generate()), UserId.generate(), "A")

    @pytest.mark.asyncio
    async def test_match_not_in_progress(self, uow, scoring_service):
        a, b = _make_player(), _make_player()
        match = Match.create(round_id=RoundId.generate(), match_number=1, team_a_players=[a], team_b_players=[b])
        await uow.matches.add(match)
        uc = ConcedeMatchUseCase(uow, scoring_service)
        with pytest.raises(MatchNotScoringError):
            await uc.execute(str(match.id), a.user_id, "A")

    @pytest.mark.asyncio
    async def test_not_player_not_creator(self, uow, scoring_service):
        a, b = _make_player(), _make_player()
        creator = UserId.generate()
        match, mock_round, mock_comp = _setup(uow, a, b, creator)
        await uow.matches.add(match)
        uow._rounds._rounds[mock_round.id] = mock_round
        uow._competitions._competitions[mock_comp.id] = mock_comp

        uc = ConcedeMatchUseCase(uow, scoring_service)
        outsider = UserId.generate()
        with pytest.raises(NotMatchPlayerError):
            await uc.execute(str(match.id), outsider, "A")

    @pytest.mark.asyncio
    async def test_player_cannot_concede_opponent_team(self, uow, scoring_service):
        a, b = _make_player(), _make_player()
        creator = UserId.generate()
        match, mock_round, mock_comp = _setup(uow, a, b, creator)
        await uow.matches.add(match)
        uow._rounds._rounds[mock_round.id] = mock_round
        uow._competitions._competitions[mock_comp.id] = mock_comp

        uc = ConcedeMatchUseCase(uow, scoring_service)
        with pytest.raises(NotMatchPlayerError, match="Solo puedes conceder tu propio equipo"):
            await uc.execute(str(match.id), a.user_id, "B")


class TestConcedeMatchHappyPath:
    @pytest.mark.asyncio
    async def test_player_concedes_own_team(self, uow, scoring_service):
        a, b = _make_player(), _make_player()
        creator = UserId.generate()
        match, mock_round, mock_comp = _setup(uow, a, b, creator)
        await uow.matches.add(match)
        uow._rounds._rounds[mock_round.id] = mock_round
        uow._competitions._competitions[mock_comp.id] = mock_comp

        uc = ConcedeMatchUseCase(uow, scoring_service)
        result = await uc.execute(str(match.id), a.user_id, "A", reason="Injury")
        assert result["new_status"] == "CONCEDED"
        assert result["result"]["winner"] == "B"

    @pytest.mark.asyncio
    async def test_creator_concedes_any_team(self, uow, scoring_service):
        a, b = _make_player(), _make_player()
        creator = UserId.generate()
        match, mock_round, mock_comp = _setup(uow, a, b, creator)
        await uow.matches.add(match)
        uow._rounds._rounds[mock_round.id] = mock_round
        uow._competitions._competitions[mock_comp.id] = mock_comp

        uc = ConcedeMatchUseCase(uow, scoring_service)
        result = await uc.execute(str(match.id), creator, "B")
        assert result["new_status"] == "CONCEDED"
        assert result["result"]["winner"] == "A"
