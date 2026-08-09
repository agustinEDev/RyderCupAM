"""
Tests del resumen de rendimiento de un jugador (BE #128).

Lo que más importa aquí es la regla de #127: una partida rápida que alguien
ocultó de su historial tampoco cuenta para SUS estadísticas, pero sigue
contando para el resto de participantes. El ocultado es por persona, no de la
partida entera.
"""

from datetime import date, timedelta
from uuid import uuid4

import pytest

from src.modules.competition.domain.entities.competition import Competition
from src.modules.competition.domain.entities.hole_score import HoleScore
from src.modules.competition.domain.entities.match import Match
from src.modules.competition.domain.entities.round import Round
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.competition_name import CompetitionName
from src.modules.competition.domain.value_objects.date_range import DateRange
from src.modules.competition.domain.value_objects.location import Location
from src.modules.competition.domain.value_objects.match_format import MatchFormat
from src.modules.competition.domain.value_objects.match_player import MatchPlayer
from src.modules.competition.domain.value_objects.play_mode import PlayMode
from src.modules.competition.domain.value_objects.session_type import SessionType
from src.modules.competition.infrastructure.persistence.in_memory.in_memory_unit_of_work import (
    InMemoryUnitOfWork as InMemoryCompetitionUnitOfWork,
)
from src.modules.golf_course.domain.entities.golf_course import GolfCourse
from src.modules.golf_course.domain.entities.hole import Hole
from src.modules.golf_course.domain.entities.tee import Tee
from src.modules.golf_course.domain.value_objects.course_type import CourseType
from src.modules.golf_course.domain.value_objects.tee_category import TeeCategory
from src.modules.golf_course.infrastructure.persistence.in_memory.in_memory_golf_course_unit_of_work import (
    InMemoryGolfCourseUnitOfWork,
)
from src.modules.quick_match.domain.entities.quick_match import QuickMatch
from src.modules.quick_match.domain.entities.quick_match_hole_score import QuickMatchHoleScore
from src.modules.quick_match.domain.value_objects.quick_match_hole_score_id import (
    QuickMatchHoleScoreId,
)
from src.modules.quick_match.domain.value_objects.quick_match_id import QuickMatchId
from src.modules.quick_match.domain.value_objects.quick_match_participant import (
    QuickMatchParticipant,
)
from src.modules.quick_match.domain.value_objects.scoring_format import ScoringFormat
from src.modules.quick_match.infrastructure.persistence.in_memory.in_memory_quick_match_unit_of_work import (
    InMemoryQuickMatchUnitOfWork,
)
from src.modules.user.application.use_cases.get_player_stats_use_case import (
    GetPlayerStatsUseCase,
)
from src.modules.user.domain.entities.user import User
from src.modules.user.infrastructure.persistence.in_memory.in_memory_unit_of_work import (
    InMemoryUnitOfWork as InMemoryUserUnitOfWork,
)
from src.shared.domain.value_objects.country_code import CountryCode
from src.shared.domain.value_objects.gender import Gender


@pytest.fixture
def competition_uow():
    return InMemoryCompetitionUnitOfWork()


@pytest.fixture
def qm_uow():
    return InMemoryQuickMatchUnitOfWork()


@pytest.fixture
def golf_course_uow():
    return InMemoryGolfCourseUnitOfWork()


@pytest.fixture
def user_uow():
    return InMemoryUserUnitOfWork()


def unique_email(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:8]}@test.com"


async def create_user(user_uow, email: str, handicap: float | None = None):
    user = User.create(
        first_name="Test",
        last_name="User",
        email_str=email,
        plain_password="SecureP@ssw0rd123",
    )
    if handicap is not None:
        user.update_handicap(handicap)
    async with user_uow:
        await user_uow.users.save(user)
    return user


async def create_golf_course(golf_course_uow, creator_id):
    """Campo de par 72: 18 hoyos de par 4, stroke index 1 a 18."""
    tees = [
        Tee(
            category=TeeCategory.AMATEUR,
            gender=Gender.MALE,
            identifier="Yellow",
            course_rating=70.0,
            slope_rating=125,
        ),
        Tee(
            category=TeeCategory.CHAMPIONSHIP,
            gender=Gender.MALE,
            identifier="White",
            course_rating=72.0,
            slope_rating=130,
        ),
    ]
    holes = [Hole(number=i, par=4, stroke_index=i) for i in range(1, 19)]

    golf_course = GolfCourse.create(
        name="Test Golf Club",
        country_code=CountryCode("ES"),
        course_type=CourseType.STANDARD_18,
        creator_id=creator_id,
        tees=tees,
        holes=holes,
    )
    golf_course.approve()
    async with golf_course_uow:
        await golf_course_uow.golf_courses.save(golf_course)
    return golf_course


def _use_case(user_uow, competition_uow, qm_uow, golf_course_uow):
    return GetPlayerStatsUseCase(
        user_uow=user_uow,
        competition_uow=competition_uow,
        quick_match_uow=qm_uow,
        golf_course_uow=golf_course_uow,
    )


async def _played_quick_match(qm_uow, golf_course, user, *, strokes_per_hole: int = 4, others=()):
    """
    Una partida rápida terminada con la vuelta entera anotada.

    `create()` mete al creador como primer participante, así que su
    `participant_id` se lee de la entidad en vez de construirlo aquí.
    """
    match = QuickMatch.create(
        id=QuickMatchId.generate(),
        creator_id=user.id,
        golf_course_id=golf_course.id,
        scoring_format=ScoringFormat.MEDAL,
    )
    for participant in others:
        match.add_participant(participant)

    creator_participant_id = match.participants[0].participant_id
    match.start(scorer_ids=[creator_participant_id])
    match.complete()

    async with qm_uow:
        await qm_uow.quick_matches.add(match)
        for hole_number in range(1, 19):
            await qm_uow.quick_match_hole_scores.add(
                QuickMatchHoleScore(
                    id=QuickMatchHoleScoreId.generate(),
                    quick_match_id=match.id,
                    hole_number=hole_number,
                    participant_id=creator_participant_id,
                    score=strokes_per_hole,
                    recorded_by_participant_id=creator_participant_id,
                )
            )
        await qm_uow.commit()

    return match


async def _played_competition_match(
    competition_uow,
    golf_course,
    player,
    rival,
    *,
    strokes_per_hole: int | None = 4,
    strokes_received_per_hole: int = 0,
    holes_played: int = 18,
    round_date: date = date(2026, 6, 1),
):
    """
    Un partido de torneo terminado con la tarjeta del jugador anotada.

    `strokes_per_hole=None` deja los hoyos sin anotar, que es como queda un
    hoyo concedido en match play.
    """
    competition = Competition.create(
        id=CompetitionId(uuid4()),
        creator_id=player.id,
        name=CompetitionName("Ryder Cup Test"),
        dates=DateRange(start_date=round_date, end_date=round_date + timedelta(days=2)),
        location=Location(main_country=CountryCode("ES")),
        play_mode=PlayMode.SCRATCH,
        team_1_name="Team A",
        team_2_name="Team B",
    )
    round_ = Round.create(
        competition_id=competition.id,
        golf_course_id=golf_course.id,
        round_date=round_date,
        session_type=SessionType.MORNING,
        match_format=MatchFormat.SINGLES,
    )

    def match_player(user_id):
        return MatchPlayer(
            user_id=user_id,
            playing_handicap=strokes_received_per_hole * 18,
            tee_category=TeeCategory.AMATEUR,
            tee_gender=Gender.MALE,
            strokes_received=tuple(range(1, 19)) * max(strokes_received_per_hole, 1),
        )

    match = Match.create(
        round_id=round_.id,
        match_number=1,
        team_a_players=[match_player(player.id)],
        team_b_players=[match_player(rival.id)],
    )
    match.start()
    match.complete({"winner": "A", "score": "2UP"})

    async with competition_uow:
        await competition_uow.competitions.add(competition)
        await competition_uow.rounds.add(round_)
        await competition_uow.matches.add(match)
        for hole_number in range(1, holes_played + 1):
            hole_score = HoleScore.create(
                match_id=match.id,
                hole_number=hole_number,
                player_user_id=player.id,
                team="A",
                strokes_received=strokes_received_per_hole,
            )
            if strokes_per_hole is not None:
                hole_score.set_own_score(strokes_per_hole)
            await competition_uow.hole_scores.add(hole_score)
        await competition_uow.commit()

    return match


@pytest.mark.asyncio
class TestEmptyAccount:
    """Una cuenta recién creada no puede reventar el panel."""

    async def test_new_account_returns_zeros_not_errors(
        self, user_uow, competition_uow, qm_uow, golf_course_uow
    ):
        user = await create_user(user_uow, unique_email("empty"))

        stats = await _use_case(user_uow, competition_uow, qm_uow, golf_course_uow).execute(
            user.id
        )

        assert stats.rounds_played == 0
        assert stats.tournaments_total == 0
        assert stats.tournaments_active == 0

    async def test_average_is_none_without_rounds_rather_than_zero(
        self, user_uow, competition_uow, qm_uow, golf_course_uow
    ):
        """Sin rondas no hay media que dar; cero significaría jugar al par."""
        user = await create_user(user_uow, unique_email("empty"))

        stats = await _use_case(user_uow, competition_uow, qm_uow, golf_course_uow).execute(
            user.id
        )

        assert stats.scoring_avg is None


@pytest.mark.asyncio
class TestHandicap:
    """El hándicap sale del perfil."""

    async def test_reports_the_profile_handicap(
        self, user_uow, competition_uow, qm_uow, golf_course_uow
    ):
        user = await create_user(user_uow, unique_email("hcp"), handicap=12.4)

        stats = await _use_case(user_uow, competition_uow, qm_uow, golf_course_uow).execute(
            user.id
        )

        assert stats.handicap == 12.4

    async def test_trend_is_none_because_there_is_no_history(
        self, user_uow, competition_uow, qm_uow, golf_course_uow
    ):
        """
        No existe histórico de hándicap, solo la fecha del último cambio.
        Devolver None es deliberado, no un dato que falte por rellenar.
        """
        user = await create_user(user_uow, unique_email("trend"), handicap=10.0)

        stats = await _use_case(user_uow, competition_uow, qm_uow, golf_course_uow).execute(
            user.id
        )

        assert stats.handicap_trend is None


@pytest.mark.asyncio
class TestRoundsAndAverage:
    """Rondas jugadas y media respecto al par."""

    async def test_counts_a_completed_quick_match(
        self, user_uow, competition_uow, qm_uow, golf_course_uow
    ):
        user = await create_user(user_uow, unique_email("rounds"), handicap=0)
        course = await create_golf_course(golf_course_uow, user.id)
        await _played_quick_match(qm_uow, course, user)

        stats = await _use_case(user_uow, competition_uow, qm_uow, golf_course_uow).execute(
            user.id
        )

        assert stats.rounds_played == 1

    async def test_average_is_net_against_par_not_gross_strokes(
        self, user_uow, competition_uow, qm_uow, golf_course_uow
    ):
        """
        Campo de par 72 (18 hoyos de par 4), jugador scratch, 5 golpes por
        hoyo: 90 brutos, +18 respecto al par. La media es esa, no los 90.
        """
        user = await create_user(user_uow, unique_email("avg"), handicap=0)
        course = await create_golf_course(golf_course_uow, user.id)
        await _played_quick_match(qm_uow, course, user, strokes_per_hole=5)

        stats = await _use_case(user_uow, competition_uow, qm_uow, golf_course_uow).execute(
            user.id
        )

        assert stats.scoring_avg == 18.0

    async def test_handicap_strokes_count_towards_the_average(
        self, user_uow, competition_uow, qm_uow, golf_course_uow
    ):
        """Con 18 de hándicap, 5 brutos por hoyo son par neto: media 0."""
        user = await create_user(user_uow, unique_email("net"), handicap=18.0)
        course = await create_golf_course(golf_course_uow, user.id)
        await _played_quick_match(qm_uow, course, user, strokes_per_hole=5)

        stats = await _use_case(user_uow, competition_uow, qm_uow, golf_course_uow).execute(
            user.id
        )

        assert stats.scoring_avg == 0.0


@pytest.mark.asyncio
class TestCompetitionScorecards:
    """
    Los partidos de torneo también entran en la media.

    Da igual el formato: en match play también firmas una tarjeta con tus
    golpes, y esa tarjeta dice a qué nivel jugaste igual que la de una vuelta
    de medal. Cuando existan torneos Stableford esto ya estará resuelto.
    """

    async def test_a_tournament_scorecard_counts_towards_the_average(
        self, user_uow, competition_uow, qm_uow, golf_course_uow
    ):
        """Par 72, 5 golpes por hoyo sin recibir ninguno: +18."""
        player = await create_user(user_uow, unique_email("comp"), handicap=0)
        rival = await create_user(user_uow, unique_email("rival"), handicap=0)
        course = await create_golf_course(golf_course_uow, player.id)
        await _played_competition_match(
            competition_uow, course, player, rival, strokes_per_hole=5
        )

        stats = await _use_case(user_uow, competition_uow, qm_uow, golf_course_uow).execute(
            player.id
        )

        assert stats.rounds_played == 1
        assert stats.scoring_avg == 18.0

    async def test_strokes_received_count_against_the_par(
        self, user_uow, competition_uow, qm_uow, golf_course_uow
    ):
        """Un golpe recibido por hoyo: los mismos 5 brutos son par neto."""
        player = await create_user(user_uow, unique_email("comp"), handicap=18)
        rival = await create_user(user_uow, unique_email("rival"), handicap=18)
        course = await create_golf_course(golf_course_uow, player.id)
        await _played_competition_match(
            competition_uow,
            course,
            player,
            rival,
            strokes_per_hole=5,
            strokes_received_per_hole=1,
        )

        stats = await _use_case(user_uow, competition_uow, qm_uow, golf_course_uow).execute(
            player.id
        )

        assert stats.scoring_avg == 0.0

    async def test_averages_both_sources_together(
        self, user_uow, competition_uow, qm_uow, golf_course_uow
    ):
        """Una partida rápida a +18 y un torneo al par dan una media de +9."""
        player = await create_user(user_uow, unique_email("both"), handicap=0)
        rival = await create_user(user_uow, unique_email("rival"), handicap=0)
        course = await create_golf_course(golf_course_uow, player.id)
        await _played_quick_match(qm_uow, course, player, strokes_per_hole=5)
        await _played_competition_match(
            competition_uow, course, player, rival, strokes_per_hole=4
        )

        stats = await _use_case(user_uow, competition_uow, qm_uow, golf_course_uow).execute(
            player.id
        )

        assert stats.rounds_played == 2
        assert stats.scoring_avg == 9.0

    async def test_conceded_holes_do_not_count_as_played(
        self, user_uow, competition_uow, qm_uow, golf_course_uow
    ):
        """
        En match play te conceden hoyos que ibas ganando. Rellenarlos con un
        doble bogey castigaría por ir por delante, así que se dejan fuera y la
        vuelta se mide contra el par de lo que sí se jugó.
        """
        player = await create_user(user_uow, unique_email("conceded"), handicap=0)
        rival = await create_user(user_uow, unique_email("rival"), handicap=0)
        course = await create_golf_course(golf_course_uow, player.id)
        await _played_competition_match(
            competition_uow, course, player, rival, strokes_per_hole=5, holes_played=9
        )

        stats = await _use_case(user_uow, competition_uow, qm_uow, golf_course_uow).execute(
            player.id
        )

        # Nueve hoyos a +1: la vuelta cuenta como +9, no como +18
        assert stats.rounds_played == 1
        assert stats.scoring_avg == 9.0

    async def test_a_match_without_a_single_hole_scored_is_not_averaged(
        self, user_uow, competition_uow, qm_uow, golf_course_uow
    ):
        """Se jugó (cuenta como ronda) pero no dice nada: no hay media que sacar."""
        player = await create_user(user_uow, unique_email("noscore"), handicap=0)
        rival = await create_user(user_uow, unique_email("rival"), handicap=0)
        course = await create_golf_course(golf_course_uow, player.id)
        await _played_competition_match(
            competition_uow, course, player, rival, strokes_per_hole=None
        )

        stats = await _use_case(user_uow, competition_uow, qm_uow, golf_course_uow).execute(
            player.id
        )

        assert stats.rounds_played == 1
        assert stats.scoring_avg is None

    async def test_a_disaster_hole_is_capped_at_net_double_bogey(
        self, user_uow, competition_uow, qm_uow, golf_course_uow
    ):
        """
        Regla WHS 3.1. Con 10 golpes en todos los hoyos de un par 4, la media
        se queda en +2 por hoyo (+36) en vez de en +6 (+108).
        """
        player = await create_user(user_uow, unique_email("disaster"), handicap=0)
        rival = await create_user(user_uow, unique_email("rival"), handicap=0)
        course = await create_golf_course(golf_course_uow, player.id)
        await _played_competition_match(
            competition_uow, course, player, rival, strokes_per_hole=10
        )

        stats = await _use_case(user_uow, competition_uow, qm_uow, golf_course_uow).execute(
            player.id
        )

        assert stats.scoring_avg == 36.0

    async def test_the_per_course_breakdown_also_filters_tournament_rounds(
        self, user_uow, competition_uow, qm_uow, golf_course_uow
    ):
        player = await create_user(user_uow, unique_email("bycourse"), handicap=0)
        rival = await create_user(user_uow, unique_email("rival"), handicap=0)
        played_course = await create_golf_course(golf_course_uow, player.id)
        other_course = await create_golf_course(golf_course_uow, player.id)
        await _played_competition_match(
            competition_uow, played_course, player, rival, strokes_per_hole=5
        )

        use_case = _use_case(user_uow, competition_uow, qm_uow, golf_course_uow)

        played = await use_case.execute(player.id, golf_course_id=played_course.id)
        other = await use_case.execute(player.id, golf_course_id=other_course.id)

        assert played.rounds_played == 1
        assert played.scoring_avg == 18.0
        assert other.rounds_played == 0
        assert other.scoring_avg is None


@pytest.mark.asyncio
class TestHiddenMatches:
    """Regla de #127: ocultar es por persona, no por partida."""

    async def test_a_match_hidden_by_the_caller_does_not_count_for_them(
        self, user_uow, competition_uow, qm_uow, golf_course_uow
    ):
        user = await create_user(user_uow, unique_email("hider"), handicap=0)
        course = await create_golf_course(golf_course_uow, user.id)
        match = await _played_quick_match(qm_uow, course, user)

        async with qm_uow:
            stored = await qm_uow.quick_matches.find_by_id(match.id)
            stored.hide_for(stored.participants[0].participant_id)
            await qm_uow.quick_matches.update(stored)
            await qm_uow.commit()

        stats = await _use_case(user_uow, competition_uow, qm_uow, golf_course_uow).execute(
            user.id
        )

        assert stats.rounds_played == 0
        assert stats.scoring_avg is None

    async def test_the_same_match_still_counts_for_the_other_participant(
        self, user_uow, competition_uow, qm_uow, golf_course_uow
    ):
        """
        Lo que hace útil la regla: si ocultar una partida la borrase para todos,
        cualquiera podría alterar las estadísticas de los demás.
        """
        hider = await create_user(user_uow, unique_email("hider"), handicap=0)
        other = await create_user(user_uow, unique_email("other"), handicap=0)
        course = await create_golf_course(golf_course_uow, hider.id)

        other_participant = QuickMatchParticipant.for_user(other.id)
        match = await _played_quick_match(
            qm_uow, course, hider, others=[other_participant]
        )

        async with qm_uow:
            stored = await qm_uow.quick_matches.find_by_id(match.id)
            stored.hide_for(stored.participants[0].participant_id)
            await qm_uow.quick_matches.update(stored)
            await qm_uow.commit()

        use_case = _use_case(user_uow, competition_uow, qm_uow, golf_course_uow)

        assert (await use_case.execute(hider.id)).rounds_played == 0
        assert (await use_case.execute(other.id)).rounds_played == 1
