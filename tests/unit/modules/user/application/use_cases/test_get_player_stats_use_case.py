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


async def _played_quick_match(
    qm_uow,
    golf_course,
    user,
    *,
    strokes_per_hole: int = 4,
    others=(),
    holes_played: int = 18,
):
    """
    Una partida rápida terminada con la vuelta anotada.

    `create()` mete al creador como primer participante, así que su
    `participant_id` se lee de la entidad en vez de construirlo aquí.
    `holes_played` deja la tarjeta a medias.
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
        # Todos firman su vuelta: una tarjeta a medias no computa
        for participant in match.participants:
            for hole_number in range(1, holes_played + 1):
                await qm_uow.quick_match_hole_scores.add(
                    QuickMatchHoleScore(
                        id=QuickMatchHoleScoreId.generate(),
                        quick_match_id=match.id,
                        hole_number=hole_number,
                        participant_id=participant.participant_id,
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
    unscored_holes: list[int] | None = None,
    decided_early: bool = False,
    round_date: date = date(2026, 6, 1),
):
    """
    Un partido de torneo terminado con la tarjeta del jugador anotada.

    `strokes_per_hole=None` deja la tarjeta entera sin anotar; `holes_played`
    la corta antes del 18 (partido cerrado antes de tiempo) y `unscored_holes`
    deja huecos sueltos, que es como queda un hoyo concedido en match play.
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
    if decided_early:
        # Matemáticamente ganado en el 15: 4 arriba y 3 por jugar
        match.mark_decided({"winner": "A", "score": "4&3"})
    match.complete({"winner": "A", "score": "4&3" if decided_early else "2UP"})

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
            if strokes_per_hole is not None and hole_number not in (unscored_holes or []):
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
class TestIncompleteQuickMatchCards:
    """Media vuelta no es una vuelta, tampoco en partida rápida."""

    async def test_a_partial_card_counts_for_nothing(
        self, user_uow, competition_uow, qm_uow, golf_course_uow
    ):
        user = await create_user(user_uow, unique_email("partial"), handicap=0)
        course = await create_golf_course(golf_course_uow, user.id)
        await _played_quick_match(qm_uow, course, user, strokes_per_hole=5, holes_played=9)

        stats = await _use_case(user_uow, competition_uow, qm_uow, golf_course_uow).execute(
            user.id
        )

        assert stats.rounds_played == 0
        assert stats.scoring_avg is None

    async def test_a_match_still_in_progress_counts_for_nothing(
        self, user_uow, competition_uow, qm_uow, golf_course_uow
    ):
        """La vuelta está entera, pero la partida sigue abierta."""
        user = await create_user(user_uow, unique_email("open"), handicap=0)
        course = await create_golf_course(golf_course_uow, user.id)
        match = QuickMatch.create(
            id=QuickMatchId.generate(),
            creator_id=user.id,
            golf_course_id=course.id,
            scoring_format=ScoringFormat.MEDAL,
        )
        participant_id = match.participants[0].participant_id
        match.start(scorer_ids=[participant_id])

        async with qm_uow:
            await qm_uow.quick_matches.add(match)
            for hole_number in range(1, 19):
                await qm_uow.quick_match_hole_scores.add(
                    QuickMatchHoleScore(
                        id=QuickMatchHoleScoreId.generate(),
                        quick_match_id=match.id,
                        hole_number=hole_number,
                        participant_id=participant_id,
                        score=5,
                        recorded_by_participant_id=participant_id,
                    )
                )
            await qm_uow.commit()

        stats = await _use_case(user_uow, competition_uow, qm_uow, golf_course_uow).execute(
            user.id
        )

        assert stats.rounds_played == 0
        assert stats.scoring_avg is None


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

    async def test_a_match_decided_early_counts_if_the_card_was_finished_anyway(
        self, user_uow, competition_uow, qm_uow, golf_course_uow
    ):
        """
        Lo que decide es la tarjeta, no en qué hoyo se ganó el partido. Si el
        partido se resolvió en el 15 pero los jugadores siguieron anotando
        hasta el 18, la vuelta está entera y computa como cualquier otra.
        """
        player = await create_user(user_uow, unique_email("decided"), handicap=0)
        rival = await create_user(user_uow, unique_email("rival"), handicap=0)
        course = await create_golf_course(golf_course_uow, player.id)
        await _played_competition_match(
            competition_uow, course, player, rival, strokes_per_hole=5, decided_early=True
        )

        stats = await _use_case(user_uow, competition_uow, qm_uow, golf_course_uow).execute(
            player.id
        )

        assert stats.rounds_played == 1
        assert stats.scoring_avg == 18.0

    async def test_a_match_closed_before_the_18th_does_not_count(
        self, user_uow, competition_uow, qm_uow, golf_course_uow
    ):
        """
        El mismo partido resuelto pronto, pero dejando de anotar al cerrarse:
        la tarjeta se queda sin hoyos, y media vuelta no se puede comparar con
        una entera. Es el precio de que la media hable de rondas iguales.
        """
        player = await create_user(user_uow, unique_email("conceded"), handicap=0)
        rival = await create_user(user_uow, unique_email("rival"), handicap=0)
        course = await create_golf_course(golf_course_uow, player.id)
        await _played_competition_match(
            competition_uow, course, player, rival, strokes_per_hole=5, holes_played=15
        )

        stats = await _use_case(user_uow, competition_uow, qm_uow, golf_course_uow).execute(
            player.id
        )

        assert stats.rounds_played == 0
        assert stats.scoring_avg is None

    async def test_a_single_conceded_hole_invalidates_the_card(
        self, user_uow, competition_uow, qm_uow, golf_course_uow
    ):
        """
        Los 18 hoyos existen en la tarjeta, pero uno se quedó sin anotar. No se
        rellena con un doble bogey ni se ignora: la vuelta no computa.
        """
        player = await create_user(user_uow, unique_email("gap"), handicap=0)
        rival = await create_user(user_uow, unique_email("rival"), handicap=0)
        course = await create_golf_course(golf_course_uow, player.id)
        await _played_competition_match(
            competition_uow, course, player, rival, strokes_per_hole=5, unscored_holes=[7]
        )

        stats = await _use_case(user_uow, competition_uow, qm_uow, golf_course_uow).execute(
            player.id
        )

        assert stats.rounds_played == 0
        assert stats.scoring_avg is None

    async def test_a_match_without_a_single_hole_scored_does_not_count(
        self, user_uow, competition_uow, qm_uow, golf_course_uow
    ):
        player = await create_user(user_uow, unique_email("noscore"), handicap=0)
        rival = await create_user(user_uow, unique_email("rival"), handicap=0)
        course = await create_golf_course(golf_course_uow, player.id)
        await _played_competition_match(
            competition_uow, course, player, rival, strokes_per_hole=None
        )

        stats = await _use_case(user_uow, competition_uow, qm_uow, golf_course_uow).execute(
            player.id
        )

        assert stats.rounds_played == 0
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
