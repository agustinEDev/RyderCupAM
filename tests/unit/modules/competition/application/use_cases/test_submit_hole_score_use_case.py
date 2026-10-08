"""Tests para SubmitHoleScoreUseCase."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.modules.competition.application.dto.scoring_dto import SubmitHoleScoreBodyDTO
from src.modules.competition.application.exceptions import (
    InvalidHoleNumberError,
    MatchNotFoundError,
    MatchNotScoringError,
    NotMatchPlayerError,
    NotYourMarkedPlayerError,
)
from src.modules.competition.application.use_cases.submit_hole_score_use_case import (
    SubmitHoleScoreUseCase,
)
from src.modules.competition.domain.entities.hole_score import HoleScore
from src.modules.competition.domain.entities.match import Match
from src.modules.competition.domain.services.scoring_service import ScoringService
from src.modules.competition.domain.value_objects.marker_assignment import MarkerAssignment
from src.modules.competition.domain.value_objects.match_player import MatchPlayer
from src.modules.competition.domain.value_objects.match_status import MatchStatus
from src.modules.competition.domain.value_objects.round_id import RoundId
from src.modules.competition.domain.value_objects.validation_status import ValidationStatus
from src.modules.competition.infrastructure.persistence.in_memory.in_memory_unit_of_work import (
    InMemoryUnitOfWork,
)
from src.modules.golf_course.domain.value_objects.tee_color import TeeColor
from src.modules.user.domain.value_objects.user_id import UserId
from src.shared.domain.value_objects.match_format import MatchFormat


def _make_player(user_id=None, handicap=10, strokes=()):
    return MatchPlayer.create(
        user_id=user_id or UserId.generate(),
        playing_handicap=handicap,
        tee_color=TeeColor.YELLOW,
        strokes_received=list(strokes),
    )


def _setup_match(
    uow,
    team_a,
    team_b,
    status=MatchStatus.IN_PROGRESS,
    match_format=MatchFormat.SINGLES,
    marker_assignments=None,
):
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
        # La vista de anotación pinta `display_name` (BE #239): sin esto el
        # mock devuelve otro MagicMock y el DTO lo rechaza por no ser texto
        user.display_name = f"Player {str(uid)[:8]}"
        user.display_name_or_legal = MagicMock(return_value=f"Player {str(uid)[:8]}")
        return user

    repo = AsyncMock()
    repo.find_by_id = AsyncMock(side_effect=_make_mock_user)
    return repo


class TestSubmitHoleScoreValidation:
    @pytest.mark.asyncio
    async def test_match_not_found(self, uow, user_repo, scoring_service):
        uc = SubmitHoleScoreUseCase(uow, user_repo, scoring_service)
        body = SubmitHoleScoreBodyDTO(
            own_score=5, marked_player_id=str(UserId.generate()), marked_score=4
        )
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
    async def test_scorecard_submitted_skips_own_score_allows_marker(
        self, uow, user_repo, scoring_service
    ):
        """Tras entregar tarjeta, own_score se ignora silenciosamente y marker_score se procesa."""
        a, b = _make_player(), _make_player()
        assignments = [
            MarkerAssignment(
                scorer_user_id=a.user_id, marks_user_id=b.user_id, marked_by_user_id=b.user_id
            ),
            MarkerAssignment(
                scorer_user_id=b.user_id, marks_user_id=a.user_id, marked_by_user_id=a.user_id
            ),
        ]
        match, mock_round = _setup_match(uow, [a], [b], marker_assignments=assignments)
        await uow.matches.add(match)
        uow._rounds._rounds[mock_round.id] = mock_round

        # Pre-create hole scores con own_score existente
        hs_a = HoleScore.create(
            match_id=match.id, hole_number=1, player_user_id=a.user_id, team="A", strokes_received=0
        )
        hs_b = HoleScore.create(
            match_id=match.id, hole_number=1, player_user_id=b.user_id, team="B", strokes_received=0
        )
        hs_a.set_own_score(4)
        await uow.hole_scores.add(hs_a)
        await uow.hole_scores.add(hs_b)

        # Entregar tarjeta de A
        match.submit_scorecard(a.user_id, MatchFormat.SINGLES)
        await uow.matches.update(match)

        # Mock competition for scoring view
        mock_comp = MagicMock()
        mock_comp.id = mock_round.competition_id
        mock_comp.ryder_cup.team_1_name = "Team A"
        mock_comp.ryder_cup.team_2_name = "Team B"
        mock_comp.require_ryder_cup.return_value = mock_comp.ryder_cup
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
    async def test_marked_player_scorecard_submitted_skips_marker_allows_own(
        self, uow, user_repo, scoring_service
    ):
        """Si el jugador que marcas ya entregó tarjeta, marker_score se ignora y own_score se procesa."""
        a, b = _make_player(), _make_player()
        assignments = [
            MarkerAssignment(
                scorer_user_id=a.user_id, marks_user_id=b.user_id, marked_by_user_id=b.user_id
            ),
            MarkerAssignment(
                scorer_user_id=b.user_id, marks_user_id=a.user_id, marked_by_user_id=a.user_id
            ),
        ]
        match, mock_round = _setup_match(uow, [a], [b], marker_assignments=assignments)
        await uow.matches.add(match)
        uow._rounds._rounds[mock_round.id] = mock_round

        # Pre-create hole scores con marker_score existente en B
        hs_a = HoleScore.create(
            match_id=match.id, hole_number=1, player_user_id=a.user_id, team="A", strokes_received=0
        )
        hs_b = HoleScore.create(
            match_id=match.id, hole_number=1, player_user_id=b.user_id, team="B", strokes_received=0
        )
        hs_b.set_marker_score(3)
        await uow.hole_scores.add(hs_a)
        await uow.hole_scores.add(hs_b)

        # B entrega tarjeta
        match.submit_scorecard(b.user_id, MatchFormat.SINGLES)
        await uow.matches.update(match)

        # Mock competition for scoring view
        mock_comp = MagicMock()
        mock_comp.id = mock_round.competition_id
        mock_comp.ryder_cup.team_1_name = "Team A"
        mock_comp.ryder_cup.team_2_name = "Team B"
        mock_comp.require_ryder_cup.return_value = mock_comp.ryder_cup
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
            MarkerAssignment(
                scorer_user_id=a.user_id, marks_user_id=b.user_id, marked_by_user_id=b.user_id
            ),
            MarkerAssignment(
                scorer_user_id=b.user_id, marks_user_id=a.user_id, marked_by_user_id=a.user_id
            ),
        ]
        match, mock_round = _setup_match(uow, [a], [b], marker_assignments=assignments)
        await uow.matches.add(match)
        uow._rounds._rounds[mock_round.id] = mock_round

        # Pre-create hole scores
        hs_a = HoleScore.create(
            match_id=match.id, hole_number=1, player_user_id=a.user_id, team="A", strokes_received=0
        )
        hs_b = HoleScore.create(
            match_id=match.id, hole_number=1, player_user_id=b.user_id, team="B", strokes_received=0
        )
        await uow.hole_scores.add(hs_a)
        await uow.hole_scores.add(hs_b)

        # Mock competition for scoring view
        mock_comp = MagicMock()
        mock_comp.id = mock_round.competition_id
        mock_comp.ryder_cup.team_1_name = "Team A"
        mock_comp.ryder_cup.team_2_name = "Team B"
        mock_comp.require_ryder_cup.return_value = mock_comp.ryder_cup
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


def _crossed_assignments(a, b):
    return [
        MarkerAssignment(
            scorer_user_id=a.user_id, marks_user_id=b.user_id, marked_by_user_id=b.user_id
        ),
        MarkerAssignment(
            scorer_user_id=b.user_id, marks_user_id=a.user_id, marked_by_user_id=a.user_id
        ),
    ]


async def _match_with_hole_rows(uow, hole_number=1):
    """Partido en juego, marcadores cruzados y las filas del hoyo ya creadas."""
    a, b = _make_player(), _make_player()
    match, mock_round = _setup_match(uow, [a], [b], marker_assignments=_crossed_assignments(a, b))
    await uow.matches.add(match)
    uow._rounds._rounds[mock_round.id] = mock_round

    for player, team in ((a, "A"), (b, "B")):
        await uow.hole_scores.add(
            HoleScore.create(
                match_id=match.id,
                hole_number=hole_number,
                player_user_id=player.user_id,
                team=team,
                strokes_received=0,
            )
        )

    mock_comp = MagicMock()
    mock_comp.id = mock_round.competition_id
    mock_comp.ryder_cup.team_1_name = "Team A"
    mock_comp.ryder_cup.team_2_name = "Team B"
    mock_comp.require_ryder_cup.return_value = mock_comp.ryder_cup
    uow._competitions._competitions[mock_comp.id] = mock_comp

    return match, a, b


class TestSubmitHoleScoreOmittedFields:
    """Un score que no viene en el body no se toca (#301).

    Nulo SI es un hoyo recogido —conceder, en match play—, asi que omitir y
    mandar nulo no pueden significar lo mismo: hoy los dos dejan el hoyo del
    otro concedido sin que nadie lo conceda.
    """

    @pytest.mark.asyncio
    async def test_own_score_only_leaves_the_marked_player_untouched(
        self, uow, user_repo, scoring_service
    ):
        """
        Given un hoyo sin anotar por nadie
        When llega own_score y marked_score NO viene en el body
        Then la fila del jugador marcado se queda sin tocar
        """
        match, a, b = await _match_with_hole_rows(uow)
        uc = SubmitHoleScoreUseCase(uow, user_repo, scoring_service)
        body = SubmitHoleScoreBodyDTO(own_score=4, marked_player_id=str(b.user_id))

        await uc.execute(str(match.id), 1, body, a.user_id)

        marked = await uow.hole_scores.find_one(match.id, 1, b.user_id)
        assert marked.marker_submitted is False
        assert marked.marker_score is None
        own = await uow.hole_scores.find_one(match.id, 1, a.user_id)
        assert own.own_score == 4
        assert own.own_submitted is True

    @pytest.mark.asyncio
    async def test_marked_score_only_leaves_the_player_untouched(
        self, uow, user_repo, scoring_service
    ):
        """
        Given un hoyo sin anotar por nadie
        When llega marked_score y own_score NO viene en el body
        Then la fila del propio jugador se queda sin tocar
        """
        match, a, b = await _match_with_hole_rows(uow)
        uc = SubmitHoleScoreUseCase(uow, user_repo, scoring_service)
        body = SubmitHoleScoreBodyDTO(marked_player_id=str(b.user_id), marked_score=5)

        await uc.execute(str(match.id), 1, body, a.user_id)

        own = await uow.hole_scores.find_one(match.id, 1, a.user_id)
        assert own.own_submitted is False
        assert own.own_score is None
        marked = await uow.hole_scores.find_one(match.id, 1, b.user_id)
        assert marked.marker_score == 5
        assert marked.marker_submitted is True

    @pytest.mark.asyncio
    async def test_an_explicit_null_own_score_is_still_a_picked_up_hole(
        self, uow, user_repo, scoring_service
    ):
        """
        Given un hoyo sin anotar
        When own_score viene en el body con valor nulo (la raya)
        Then el hoyo queda recogido, y la fila del marcado sin tocar
        """
        match, a, b = await _match_with_hole_rows(uow)
        uc = SubmitHoleScoreUseCase(uow, user_repo, scoring_service)
        body = SubmitHoleScoreBodyDTO(own_score=None, marked_player_id=str(b.user_id))

        await uc.execute(str(match.id), 1, body, a.user_id)

        own = await uow.hole_scores.find_one(match.id, 1, a.user_id)
        assert own.own_submitted is True
        assert own.own_score is None
        marked = await uow.hole_scores.find_one(match.id, 1, b.user_id)
        assert marked.marker_submitted is False

    @pytest.mark.asyncio
    async def test_an_explicit_null_marked_score_is_still_a_picked_up_hole(
        self, uow, user_repo, scoring_service
    ):
        """
        Given un hoyo sin anotar
        When marked_score viene en el body con valor nulo
        Then el hoyo del marcado queda recogido, y el propio sin tocar
        """
        match, a, b = await _match_with_hole_rows(uow)
        uc = SubmitHoleScoreUseCase(uow, user_repo, scoring_service)
        body = SubmitHoleScoreBodyDTO(marked_player_id=str(b.user_id), marked_score=None)

        await uc.execute(str(match.id), 1, body, a.user_id)

        marked = await uow.hole_scores.find_one(match.id, 1, b.user_id)
        assert marked.marker_submitted is True
        assert marked.marker_score is None
        own = await uow.hole_scores.find_one(match.id, 1, a.user_id)
        assert own.own_submitted is False

    @pytest.mark.asyncio
    async def test_a_body_with_no_scores_changes_nothing(self, uow, user_repo, scoring_service):
        """
        Given un hoyo sin anotar
        When el body solo trae marked_player_id
        Then no se anota nada en ninguna de las dos filas
        """
        match, a, b = await _match_with_hole_rows(uow)
        uc = SubmitHoleScoreUseCase(uow, user_repo, scoring_service)
        body = SubmitHoleScoreBodyDTO(marked_player_id=str(b.user_id))

        await uc.execute(str(match.id), 1, body, a.user_id)

        own = await uow.hole_scores.find_one(match.id, 1, a.user_id)
        marked = await uow.hole_scores.find_one(match.id, 1, b.user_id)
        assert own.own_submitted is False
        assert marked.marker_submitted is False

    @pytest.mark.asyncio
    async def test_own_score_only_does_not_put_the_other_hole_in_mismatch(
        self, uow, user_repo, scoring_service
    ):
        """
        Given que el jugador marcado ya anoto su propio score
        When llega own_score del otro sin marked_score
        Then su hoyo sigue PENDING y no pasa a MISMATCH
        """
        match, a, b = await _match_with_hole_rows(uow)
        marked_row = await uow.hole_scores.find_one(match.id, 1, b.user_id)
        marked_row.set_own_score(4)
        marked_row.recalculate_validation()
        await uow.hole_scores.update(marked_row)

        uc = SubmitHoleScoreUseCase(uow, user_repo, scoring_service)
        body = SubmitHoleScoreBodyDTO(own_score=5, marked_player_id=str(b.user_id))

        await uc.execute(str(match.id), 1, body, a.user_id)

        marked = await uow.hole_scores.find_one(match.id, 1, b.user_id)
        assert marked.own_score == 4
        assert marked.marker_submitted is False
        assert marked.validation_status.value == "PENDING"


class TestLaBolaDelBandoEnFoursomes:
    """BE #377: en foursomes la tarjeta es del bando. Si el compañero ya la
    entregó, lo que mande el otro no cambia la bola del bando."""

    @pytest.mark.asyncio
    async def test_u3_entregada_por_el_companero_la_bola_ya_no_cambia(
        self, uow, user_repo, scoring_service
    ):
        a1, a2, b1, b2 = (_make_player() for _ in range(4))
        assignments = [
            MarkerAssignment(
                scorer_user_id=a2.user_id, marks_user_id=b1.user_id, marked_by_user_id=b1.user_id
            ),
            MarkerAssignment(
                scorer_user_id=b1.user_id, marks_user_id=a2.user_id, marked_by_user_id=a2.user_id
            ),
        ]
        match, mock_round = _setup_match(
            uow,
            [a1, a2],
            [b1, b2],
            match_format=MatchFormat.FOURSOMES,
            marker_assignments=assignments,
        )
        await uow.matches.add(match)
        uow._rounds._rounds[mock_round.id] = mock_round
        for jugador, equipo in ((a1, "A"), (a2, "A"), (b1, "B"), (b2, "B")):
            hoyo = HoleScore.create(
                match_id=match.id,
                hole_number=1,
                player_user_id=jugador.user_id,
                team=equipo,
                strokes_received=0,
            )
            if equipo == "A":
                hoyo.set_own_score(4)
            await uow.hole_scores.add(hoyo)
        match.submit_scorecard(a1.user_id, MatchFormat.FOURSOMES)
        await uow.matches.update(match)
        mock_comp = MagicMock()
        mock_comp.id = mock_round.competition_id
        mock_comp.ryder_cup.team_1_name = "Team A"
        mock_comp.ryder_cup.team_2_name = "Team B"
        mock_comp.require_ryder_cup.return_value = mock_comp.ryder_cup
        uow._competitions._competitions[mock_comp.id] = mock_comp

        uc = SubmitHoleScoreUseCase(uow, user_repo, scoring_service)
        body = SubmitHoleScoreBodyDTO(own_score=7, marked_player_id=str(b1.user_id), marked_score=5)
        await uc.execute(str(match.id), 1, body, a2.user_id)

        for jugador in (a1, a2):
            assert (await uow.hole_scores.find_one(match.id, 1, jugador.user_id)).own_score == 4


async def _partido_con_filas(
    uow, team_a, team_b, match_format, assignments, status=MatchStatus.IN_PROGRESS
):
    """Partido con las filas del hoyo 1 de los cuatro (o dos) jugadores y su competición."""
    match, mock_round = _setup_match(
        uow,
        team_a,
        team_b,
        match_format=match_format,
        marker_assignments=assignments,
        status=status,
    )
    await uow.matches.add(match)
    uow._rounds._rounds[mock_round.id] = mock_round
    for jugadores, equipo in ((team_a, "A"), (team_b, "B")):
        for jugador in jugadores:
            await uow.hole_scores.add(
                HoleScore.create(
                    match_id=match.id,
                    hole_number=1,
                    player_user_id=jugador.user_id,
                    team=equipo,
                    strokes_received=0,
                )
            )
    mock_comp = MagicMock()
    mock_comp.id = mock_round.competition_id
    mock_comp.ryder_cup.team_1_name = "Team A"
    mock_comp.ryder_cup.team_2_name = "Team B"
    mock_comp.require_ryder_cup.return_value = mock_comp.ryder_cup
    uow._competitions._competitions[mock_comp.id] = mock_comp
    return match


def _cruzadas_de_cuatro(a1, a2, b1, b2):
    """Las de `ScoringService` en fourball y foursomes: A1→B1, A2→B2, B1→A2, B2→A1."""
    return [
        MarkerAssignment(
            scorer_user_id=a1.user_id, marks_user_id=b1.user_id, marked_by_user_id=b2.user_id
        ),
        MarkerAssignment(
            scorer_user_id=a2.user_id, marks_user_id=b2.user_id, marked_by_user_id=b1.user_id
        ),
        MarkerAssignment(
            scorer_user_id=b1.user_id, marks_user_id=a2.user_id, marked_by_user_id=a1.user_id
        ),
        MarkerAssignment(
            scorer_user_id=b2.user_id, marks_user_id=a1.user_id, marked_by_user_id=a2.user_id
        ),
    ]


class TestSoloMarcaSuMarcadorAsignado:
    """
    BE #520: cada uno marca SOLO al jugador que le asignó el sorteo de marcadores.

    Antes bastaba con que el marcado jugara el partido: uno podía ponerse a sí
    mismo como marcado, apuntarse el mismo número en las dos columnas y dejar
    su hoyo validado sin que nadie lo confirmara, o pisar lo que le había
    apuntado su marcador de verdad. Fuera de su asignación la petición entera
    se rechaza (403) y no se guarda nada, tampoco su propio golpe.
    """

    @pytest.mark.asyncio
    async def test_singles_marcarse_a_si_mismo_se_rechaza_y_no_guarda_nada(
        self, uow, user_repo, scoring_service
    ):
        match, a, _b = await _match_with_hole_rows(uow)
        uc = SubmitHoleScoreUseCase(uow, user_repo, scoring_service)

        body = SubmitHoleScoreBodyDTO(own_score=3, marked_player_id=str(a.user_id), marked_score=3)
        with pytest.raises(NotYourMarkedPlayerError):
            await uc.execute(str(match.id), 1, body, a.user_id)

        fila = await uow.hole_scores.find_one(match.id, 1, a.user_id)
        assert fila.own_score is None
        assert fila.marker_score is None
        assert fila.validation_status != ValidationStatus.MATCH

    @pytest.mark.asyncio
    async def test_singles_no_puede_pisar_lo_que_le_apunto_su_marcador(
        self, uow, user_repo, scoring_service
    ):
        match, a, b = await _match_with_hole_rows(uow)
        uc = SubmitHoleScoreUseCase(uow, user_repo, scoring_service)
        await uc.execute(
            str(match.id),
            1,
            SubmitHoleScoreBodyDTO(marked_player_id=str(a.user_id), marked_score=6),
            b.user_id,
        )

        with pytest.raises(NotYourMarkedPlayerError):
            await uc.execute(
                str(match.id),
                1,
                SubmitHoleScoreBodyDTO(
                    own_score=3, marked_player_id=str(a.user_id), marked_score=3
                ),
                a.user_id,
            )

        assert (await uow.hole_scores.find_one(match.id, 1, a.user_id)).marker_score == 6

    @pytest.mark.asyncio
    async def test_singles_su_marcador_asignado_si_puede(self, uow, user_repo, scoring_service):
        match, a, b = await _match_with_hole_rows(uow)
        uc = SubmitHoleScoreUseCase(uow, user_repo, scoring_service)

        await uc.execute(
            str(match.id),
            1,
            SubmitHoleScoreBodyDTO(own_score=5, marked_player_id=str(a.user_id), marked_score=4),
            b.user_id,
        )

        assert (await uow.hole_scores.find_one(match.id, 1, a.user_id)).marker_score == 4
        assert (await uow.hole_scores.find_one(match.id, 1, b.user_id)).own_score == 5

    @pytest.mark.asyncio
    @pytest.mark.parametrize("formato", [MatchFormat.FOURBALL, MatchFormat.FOURSOMES])
    @pytest.mark.parametrize("a_quien", ["a_si_mismo", "a_su_companero", "al_rival_que_no_le_toca"])
    async def test_de_cuatro_fuera_de_su_asignacion_se_rechaza(
        self, uow, user_repo, scoring_service, formato, a_quien
    ):
        a1, a2, b1, b2 = (_make_player() for _ in range(4))
        match = await _partido_con_filas(
            uow, [a1, a2], [b1, b2], formato, _cruzadas_de_cuatro(a1, a2, b1, b2)
        )
        marcado = {"a_si_mismo": a1, "a_su_companero": a2, "al_rival_que_no_le_toca": b2}[a_quien]
        uc = SubmitHoleScoreUseCase(uow, user_repo, scoring_service)

        with pytest.raises(NotYourMarkedPlayerError):
            await uc.execute(
                str(match.id),
                1,
                SubmitHoleScoreBodyDTO(
                    own_score=4, marked_player_id=str(marcado.user_id), marked_score=4
                ),
                a1.user_id,
            )

        for jugador in (a1, a2, b1, b2):
            fila = await uow.hole_scores.find_one(match.id, 1, jugador.user_id)
            assert fila.own_score is None
            assert fila.marker_score is None

    @pytest.mark.asyncio
    @pytest.mark.parametrize("formato", [MatchFormat.FOURBALL, MatchFormat.FOURSOMES])
    async def test_de_cuatro_al_que_le_toca_si(self, uow, user_repo, scoring_service, formato):
        a1, a2, b1, b2 = (_make_player() for _ in range(4))
        match = await _partido_con_filas(
            uow, [a1, a2], [b1, b2], formato, _cruzadas_de_cuatro(a1, a2, b1, b2)
        )
        uc = SubmitHoleScoreUseCase(uow, user_repo, scoring_service)

        await uc.execute(
            str(match.id),
            1,
            SubmitHoleScoreBodyDTO(own_score=4, marked_player_id=str(b1.user_id), marked_score=5),
            a1.user_id,
        )

        assert (await uow.hole_scores.find_one(match.id, 1, b1.user_id)).marker_score == 5

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("a_quien", "se_rechaza"),
        [("a_si_mismo", True), ("a_su_companero", True), ("a_un_rival", False)],
    )
    async def test_sin_asignaciones_vale_la_regla_de_fondo_solo_el_equipo_contrario(
        self, uow, user_repo, scoring_service, a_quien, se_rechaza
    ):
        """Un partido sin sorteo de marcadores (datos viejos): nunca uno mismo ni su compañero."""
        a1, a2, b1, b2 = (_make_player() for _ in range(4))
        match = await _partido_con_filas(uow, [a1, a2], [b1, b2], MatchFormat.FOURBALL, None)
        marcado = {"a_si_mismo": a1, "a_su_companero": a2, "a_un_rival": b2}[a_quien]
        uc = SubmitHoleScoreUseCase(uow, user_repo, scoring_service)
        body = SubmitHoleScoreBodyDTO(
            own_score=4, marked_player_id=str(marcado.user_id), marked_score=5
        )

        if se_rechaza:
            with pytest.raises(NotYourMarkedPlayerError):
                await uc.execute(str(match.id), 1, body, a1.user_id)
        else:
            await uc.execute(str(match.id), 1, body, a1.user_id)
            assert (await uow.hole_scores.find_one(match.id, 1, b2.user_id)).marker_score == 5

    @pytest.mark.asyncio
    async def test_se_rechaza_antes_de_abrir_el_partido(self, uow, user_repo, scoring_service):
        """Un marcado ajeno no abre el partido: se rechaza antes, como el de quien no juega."""
        programado, mock_round = _setup_match(
            uow, [_make_player()], [_make_player()], status=MatchStatus.SCHEDULED
        )
        jugador = programado.team_a_players[0]
        programado.set_marker_assignments(
            [
                MarkerAssignment(
                    scorer_user_id=jugador.user_id,
                    marks_user_id=programado.team_b_players[0].user_id,
                    marked_by_user_id=programado.team_b_players[0].user_id,
                ),
            ]
        )
        await uow.matches.add(programado)
        uow._rounds._rounds[mock_round.id] = mock_round
        uc = SubmitHoleScoreUseCase(uow, user_repo, scoring_service)

        with pytest.raises(NotYourMarkedPlayerError):
            await uc.execute(
                str(programado.id),
                1,
                SubmitHoleScoreBodyDTO(
                    own_score=4, marked_player_id=str(jugador.user_id), marked_score=4
                ),
                jugador.user_id,
            )

        assert (await uow.matches.find_by_id(programado.id)).status == MatchStatus.SCHEDULED
