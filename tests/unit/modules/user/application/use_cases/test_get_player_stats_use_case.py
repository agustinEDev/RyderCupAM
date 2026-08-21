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
from src.modules.golf_course.domain.value_objects.tee_color import TeeColor
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
            color=TeeColor.YELLOW,
            gender=Gender.MALE,
            identifier="Yellow",
            course_rating=70.0,
            slope_rating=125,
        ),
        Tee(
            color=TeeColor.WHITE,
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
    holes: list[int] | None = None,
    tee_color: TeeColor | None = None,
    tee_gender: Gender | None = None,
    scores_by_hole: dict[int, int] | None = None,
    match_format: MatchFormat | None = None,
):
    """
    Una partida rápida terminada con la vuelta anotada.

    `create()` mete al creador como primer participante, así que su
    `participant_id` se lee de la entidad en vez de construirlo aquí.
    `holes_played` deja la tarjeta a medias.

    Sin `tee_color` la partida no dice desde dónde se jugó, que es el caso
    de las partidas anteriores a que el frontend empezara a exigir el tee: esas
    cuentan para la media pero no generan diferencial.
    """
    match = QuickMatch.create(
        id=QuickMatchId.generate(),
        creator_id=user.id,
        golf_course_id=golf_course.id,
        match_format=match_format,
        scoring_format=None if match_format else ScoringFormat.MEDAL,
        creator_tee_color=tee_color,
        creator_tee_gender=tee_gender,
    )
    for participant in others:
        match.add_participant(participant)

    creator_participant_id = match.participants[0].participant_id
    match.start(scorer_ids=[creator_participant_id])
    match.complete()

    async with qm_uow:
        await qm_uow.quick_matches.add(match)
        # Todos firman su vuelta: una tarjeta a medias no computa
        scored_holes = holes if holes is not None else list(range(1, holes_played + 1))
        for participant in match.participants:
            for hole_number in scored_holes:
                await qm_uow.quick_match_hole_scores.add(
                    QuickMatchHoleScore(
                        id=QuickMatchHoleScoreId.generate(),
                        quick_match_id=match.id,
                        hole_number=hole_number,
                        participant_id=participant.participant_id,
                        score=(scores_by_hole or {}).get(hole_number, strokes_per_hole),
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
    picked_up_holes: list[int] | None = None,
    decided_early: bool = False,
    round_date: date = date(2026, 6, 1),
    match_format: MatchFormat = MatchFormat.SINGLES,
):
    """
    Un partido de torneo terminado con la tarjeta del jugador anotada.

    `strokes_per_hole=None` deja la tarjeta entera sin anotar; `holes_played`
    la corta antes del 18 (partido cerrado antes de tiempo) y `unscored_holes`
    deja huecos sueltos, que es como queda un hoyo concedido en match play.
    `picked_up_holes` los deja ANOTADOS y sin número, que es la raya: el
    jugador recogió la bola, y eso es un hoyo jugado, no un hueco.
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
        match_format=match_format,
    )

    def match_player(user_id):
        return MatchPlayer(
            user_id=user_id,
            playing_handicap=strokes_received_per_hole * 18,
            tee_color=TeeColor.YELLOW,
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
            if hole_number in (picked_up_holes or []):
                hole_score.set_own_score(None)
            elif strokes_per_hole is not None and hole_number not in (unscored_holes or []):
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
class TestFoursomesIsNotAPersonalRound:
    """
    En foursomes la pareja juega UNA bola a golpes alternos: ninguno de los dos
    ha jugado esa vuelta entera, así que no dice a qué nivel juega ninguno y no
    entra ni en la media ni en el diferencial WHS.
    """

    async def test_a_foursomes_quick_match_does_not_count_as_a_round(
        self, user_uow, competition_uow, qm_uow, golf_course_uow
    ):
        user = await create_user(user_uow, unique_email("fours"), handicap=0)
        partner = await create_user(user_uow, unique_email("mate"), handicap=0)
        rival_one = await create_user(user_uow, unique_email("riv1"), handicap=0)
        rival_two = await create_user(user_uow, unique_email("riv2"), handicap=0)
        course = await create_golf_course(golf_course_uow, user.id)
        await _played_quick_match(
            qm_uow,
            course,
            user,
            match_format=MatchFormat.FOURSOMES,
            others=[
                QuickMatchParticipant.for_user(partner.id, team="A"),
                QuickMatchParticipant.for_user(rival_one.id, team="B"),
                QuickMatchParticipant.for_user(rival_two.id, team="B"),
            ],
            tee_color=TeeColor.YELLOW,
            tee_gender=Gender.MALE,
        )

        stats = await _use_case(user_uow, competition_uow, qm_uow, golf_course_uow).execute(
            user.id
        )

        assert stats.rounds_played == 0

    async def test_a_singles_quick_match_still_counts(
        self, user_uow, competition_uow, qm_uow, golf_course_uow
    ):
        """La exclusión es de foursomes, no de las partidas por equipos."""
        user = await create_user(user_uow, unique_email("single"), handicap=0)
        course = await create_golf_course(golf_course_uow, user.id)
        await _played_quick_match(qm_uow, course, user)

        stats = await _use_case(user_uow, competition_uow, qm_uow, golf_course_uow).execute(
            user.id
        )

        assert stats.rounds_played == 1

    async def test_a_foursomes_tournament_match_does_not_count_either(
        self, user_uow, competition_uow, qm_uow, golf_course_uow
    ):
        """En torneo la bola alterna es la misma: la tarjeta no es de nadie."""
        player = await create_user(user_uow, unique_email("tfours"), handicap=0)
        rival = await create_user(user_uow, unique_email("trival"), handicap=0)
        course = await create_golf_course(golf_course_uow, player.id)
        await _played_competition_match(
            competition_uow,
            course,
            player,
            rival,
            strokes_per_hole=5,
            match_format=MatchFormat.FOURSOMES,
        )

        stats = await _use_case(user_uow, competition_uow, qm_uow, golf_course_uow).execute(
            player.id
        )

        assert stats.rounds_played == 0


@pytest.mark.asyncio
class TestIncompleteQuickMatchCards:
    """
    Qué es una vuelta y qué es una tarjeta abandonada.

    Cuentan la vuelta entera y las dos mitades limpias —los nueve de ida y los
    de vuelta—, porque media vuelta es una forma normal de jugar. No cuenta una
    tarjeta con huecos: eso no es media vuelta, es una vuelta que se dejó a
    medias, y son justo las malas las que se abandonan.
    """

    async def test_the_front_nine_count_as_a_round(
        self, user_uow, competition_uow, qm_uow, golf_course_uow
    ):
        """
        Nueve hoyos a 5 golpes en un campo de pares 4 son +9, que llevados a la
        escala de 18 son +18. Sin ese ajuste, jugar media vuelta parecería
        mejorar el juego.
        """
        user = await create_user(user_uow, unique_email("frontnine"), handicap=0)
        course = await create_golf_course(golf_course_uow, user.id)
        await _played_quick_match(qm_uow, course, user, strokes_per_hole=5, holes_played=9)

        stats = await _use_case(user_uow, competition_uow, qm_uow, golf_course_uow).execute(
            user.id
        )

        assert stats.rounds_played == 1
        assert stats.scoring_avg == 18.0

    async def test_the_back_nine_count_too(
        self, user_uow, competition_uow, qm_uow, golf_course_uow
    ):
        """Quien juega la vuelta de atrás ha jugado media vuelta igualmente."""
        user = await create_user(user_uow, unique_email("backnine"), handicap=0)
        course = await create_golf_course(golf_course_uow, user.id)
        await _played_quick_match(
            qm_uow, course, user, strokes_per_hole=5, holes=list(range(10, 19))
        )

        stats = await _use_case(user_uow, competition_uow, qm_uow, golf_course_uow).execute(
            user.id
        )

        assert stats.rounds_played == 1
        assert stats.scoring_avg == 18.0

    async def test_a_half_round_weighs_the_same_as_a_whole_one(
        self, user_uow, competition_uow, qm_uow, golf_course_uow
    ):
        """
        Una media vuelta a +18 de escala y una entera a +18 dan media de +18: la
        normalización sirve precisamente para que puedan promediarse.
        """
        user = await create_user(user_uow, unique_email("mixed"), handicap=0)
        course = await create_golf_course(golf_course_uow, user.id)
        await _played_quick_match(qm_uow, course, user, strokes_per_hole=5, holes_played=9)
        await _played_quick_match(qm_uow, course, user, strokes_per_hole=5)

        stats = await _use_case(user_uow, competition_uow, qm_uow, golf_course_uow).execute(
            user.id
        )

        assert stats.rounds_played == 2
        assert stats.scoring_avg == 18.0

    async def test_ten_holes_are_neither_a_round_nor_a_clean_half(
        self, user_uow, competition_uow, qm_uow, golf_course_uow
    ):
        user = await create_user(user_uow, unique_email("tenholes"), handicap=0)
        course = await create_golf_course(golf_course_uow, user.id)
        await _played_quick_match(qm_uow, course, user, strokes_per_hole=5, holes_played=10)

        stats = await _use_case(user_uow, competition_uow, qm_uow, golf_course_uow).execute(
            user.id
        )

        assert stats.rounds_played == 0
        assert stats.scoring_avg is None

    async def test_nine_scattered_holes_are_not_half_a_round(
        self, user_uow, competition_uow, qm_uow, golf_course_uow
    ):
        """
        Nueve hoyos sueltos son nueve hoyos sueltos. Exigir que sean una mitad
        entera es lo que impide que una vuelta abandonada entre por la puerta
        que se abrió para media vuelta.
        """
        user = await create_user(user_uow, unique_email("scattered"), handicap=0)
        course = await create_golf_course(golf_course_uow, user.id)
        await _played_quick_match(
            qm_uow, course, user, strokes_per_hole=5, holes=[1, 2, 3, 4, 5, 6, 7, 8, 18]
        )

        stats = await _use_case(user_uow, competition_uow, qm_uow, golf_course_uow).execute(
            user.id
        )

        assert stats.rounds_played == 0

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

    async def test_a_picked_up_hole_does_not_invalidate_the_card(
        self, user_uow, competition_uow, qm_uow, golf_course_uow
    ):
        """
        Given una vuelta de competicion con un hoyo recogido
        When se calculan las estadisticas
        Then la vuelta computa, con ese hoyo a doble bogey neto

        Es la diferencia con el hoyo SIN anotar de arriba: recoger es acabar el
        hoyo sin numero, y el WHS (Regla 3.1) manda anotarlo como doble bogey
        neto. Antes se filtraba por si habia numero, asi que la raya invalidaba
        la vuelta entera — y la misma vuelta contaba para la media si se jugaba
        en partida rapida y no si se jugaba en competicion.
        """
        player = await create_user(user_uow, unique_email("pickedup"), handicap=0)
        rival = await create_user(user_uow, unique_email("rival"), handicap=0)
        course = await create_golf_course(golf_course_uow, player.id)
        await _played_competition_match(
            competition_uow, course, player, rival, strokes_per_hole=5, picked_up_holes=[7]
        )

        stats = await _use_case(user_uow, competition_uow, qm_uow, golf_course_uow).execute(
            player.id
        )

        # Campo de par 4: 17 bogeys (+1 cada uno) y el hoyo recogido a doble
        # bogey neto (+2)
        assert stats.rounds_played == 1
        assert stats.scoring_avg == 19

    async def test_a_picked_up_hole_counts_the_same_as_a_double_bogey(
        self, user_uow, competition_uow, qm_uow, golf_course_uow
    ):
        """
        Given la misma vuelta con el hoyo 7 recogido o firmado con un 6
        When se comparan las medias
        Then salen iguales: recoger vale lo que un doble bogey, ni mas ni menos
        """
        recoge = await create_user(user_uow, unique_email("dash"), handicap=0)
        firma = await create_user(user_uow, unique_email("six"), handicap=0)
        rival = await create_user(user_uow, unique_email("rival"), handicap=0)
        course = await create_golf_course(golf_course_uow, recoge.id)
        await _played_competition_match(
            competition_uow, course, recoge, rival, strokes_per_hole=5, picked_up_holes=[7]
        )
        await _played_competition_match(
            competition_uow, course, firma, rival, strokes_per_hole=5
        )

        use_case = _use_case(user_uow, competition_uow, qm_uow, golf_course_uow)
        con_raya = await use_case.execute(recoge.id)
        sin_raya = await use_case.execute(firma.id)

        # La vuelta sin raya son 18 bogeys (+18); la de la raya cambia ese hoyo
        # por un doble bogey (+2 en vez de +1)
        assert sin_raya.scoring_avg == 18
        assert con_raya.scoring_avg == sin_raya.scoring_avg + 1

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


@pytest.mark.asyncio
class TestMatchesLeftOutOfStats:
    """
    El ojo (BE #242): la partida sigue en el historial pero no cuenta aqui.

    Estas pruebas son la red del cambio que separo ocultar de excluir. Antes,
    las estadisticas se apoyaban en que el listado del historial ya descartaba
    lo oculto; al hacer que ese listado devuelva las excluidas —para poder
    pintarlas marcadas— bastaba con no tocar nada mas para que volvieran a
    contar en la media, sin que fallara ni un test ni saltara ningun error.
    """

    async def test_a_match_left_out_by_the_caller_does_not_count_for_them(
        self, user_uow, competition_uow, qm_uow, golf_course_uow
    ):
        user = await create_user(user_uow, unique_email("excluder"), handicap=0)
        course = await create_golf_course(golf_course_uow, user.id)
        match = await _played_quick_match(qm_uow, course, user)

        async with qm_uow:
            stored = await qm_uow.quick_matches.find_by_id(match.id)
            stored.exclude_from_stats_for(stored.participants[0].participant_id)
            await qm_uow.quick_matches.update(stored)
            await qm_uow.commit()

        stats = await _use_case(user_uow, competition_uow, qm_uow, golf_course_uow).execute(
            user.id
        )

        assert stats.rounds_played == 0
        assert stats.scoring_avg is None
        assert stats.best_differential is None

    async def test_the_match_is_still_in_the_history(
        self, user_uow, competition_uow, qm_uow, golf_course_uow
    ):
        """La diferencia con ocultar: no cuenta, pero se sigue viendo."""
        user = await create_user(user_uow, unique_email("excluder"), handicap=0)
        course = await create_golf_course(golf_course_uow, user.id)
        match = await _played_quick_match(qm_uow, course, user)

        async with qm_uow:
            stored = await qm_uow.quick_matches.find_by_id(match.id)
            stored.exclude_from_stats_for(stored.participants[0].participant_id)
            await qm_uow.quick_matches.update(stored)
            await qm_uow.commit()

            listed = await qm_uow.quick_matches.list_for_user(user.id)

        assert [m.id for m in listed] == [match.id]

    async def test_it_still_counts_for_the_other_participant(
        self, user_uow, competition_uow, qm_uow, golf_course_uow
    ):
        """Es una marca personal: nadie puede alterar las estadisticas ajenas."""
        excluder = await create_user(user_uow, unique_email("excluder"), handicap=0)
        other = await create_user(user_uow, unique_email("other"), handicap=0)
        course = await create_golf_course(golf_course_uow, excluder.id)
        other_participant = QuickMatchParticipant.for_user(other.id)
        match = await _played_quick_match(
            qm_uow, course, excluder, others=[other_participant]
        )

        async with qm_uow:
            stored = await qm_uow.quick_matches.find_by_id(match.id)
            stored.exclude_from_stats_for(stored.participants[0].participant_id)
            await qm_uow.quick_matches.update(stored)
            await qm_uow.commit()

        use_case = _use_case(user_uow, competition_uow, qm_uow, golf_course_uow)

        assert (await use_case.execute(excluder.id)).rounds_played == 0
        assert (await use_case.execute(other.id)).rounds_played == 1


class TestScoreDifferentials:
    """
    Score Differentials y el índice estimado (BE #167).

    El campo de estas pruebas es par 72 con dos tees: AMATEUR (CR 70.0, slope
    125) y CHAMPIONSHIP (CR 72.0, slope 130). Los números esperados están
    calculados a mano con la fórmula del WHS, no copiados de la implementación:
    son la única defensa real contra que el cálculo se tuerza en silencio.
    """

    async def test_a_round_from_a_known_tee_yields_its_differential(
        self, user_uow, competition_uow, qm_uow, golf_course_uow
    ):
        """
        18 hoyos a 5 golpes son 90 brutos. El jugador de 10 recibe un golpe en
        los nueve hoyos más difíciles, así que ningún hoyo llega a su doble
        bogey neto y los golpes ajustados siguen siendo 90.

        Diferencial = (113 / 125) x (90 - 70.0) = 18.08 -> 18.1
        """
        player = await create_user(user_uow, unique_email("diff"), handicap=10.0)
        course = await create_golf_course(golf_course_uow, player.id)
        await _played_quick_match(
            qm_uow,
            course,
            player,
            strokes_per_hole=5,
            tee_color=TeeColor.YELLOW,
            tee_gender=Gender.MALE,
        )

        stats = await _use_case(user_uow, competition_uow, qm_uow, golf_course_uow).execute(
            player.id
        )

        assert stats.differentials == [18.1]
        assert stats.rounds_with_differential == 1
        assert stats.best_differential == 18.1

    async def test_the_same_round_is_worth_more_from_a_harder_tee(
        self, user_uow, competition_uow, qm_uow, golf_course_uow
    ):
        """
        Mismos 90 golpes desde CHAMPIONSHIP (CR 72.0, slope 130):
        (113 / 130) x (90 - 72.0) = 15.646... -> 15.6

        Es la razón de ser del diferencial: sin él, dos vueltas de 90 en campos
        distintos parecerían el mismo juego.
        """
        player = await create_user(user_uow, unique_email("hardtee"), handicap=10.0)
        course = await create_golf_course(golf_course_uow, player.id)
        await _played_quick_match(
            qm_uow,
            course,
            player,
            strokes_per_hole=5,
            tee_color=TeeColor.WHITE,
            tee_gender=Gender.MALE,
        )

        stats = await _use_case(user_uow, competition_uow, qm_uow, golf_course_uow).execute(
            player.id
        )

        assert stats.differentials == [15.6]

    async def test_a_disastrous_round_is_capped_at_net_double_bogey(
        self, user_uow, competition_uow, qm_uow, golf_course_uow
    ):
        """
        Ocho golpes en cada hoyo son 144 brutos, pero el WHS solo deja computar
        hasta el doble bogey neto: 7 en los nueve hoyos donde recibe golpe y 6
        en el resto, o sea 117 ajustados.

        Diferencial = (113 / 125) x (117 - 70.0) = 42.488 -> 42.5, no el 66.9
        que saldría sin topar. Ese tope es justo lo que impide que un día
        horrible marque el hándicap de una temporada.
        """
        player = await create_user(user_uow, unique_email("capped"), handicap=10.0)
        course = await create_golf_course(golf_course_uow, player.id)
        await _played_quick_match(
            qm_uow,
            course,
            player,
            strokes_per_hole=8,
            tee_color=TeeColor.YELLOW,
            tee_gender=Gender.MALE,
        )

        stats = await _use_case(user_uow, competition_uow, qm_uow, golf_course_uow).execute(
            player.id
        )

        assert stats.differentials == [42.5]

    async def test_a_round_without_a_known_tee_counts_but_has_no_differential(
        self, user_uow, competition_uow, qm_uow, golf_course_uow
    ):
        """
        Sin tee no hay Slope ni Course Rating, así que no hay diferencial que
        calcular. La vuelta sigue contando para la media: lo que no puede es
        decir a qué hándicap se jugó.
        """
        player = await create_user(user_uow, unique_email("notee"), handicap=10.0)
        course = await create_golf_course(golf_course_uow, player.id)
        await _played_quick_match(qm_uow, course, player, strokes_per_hole=5)

        stats = await _use_case(user_uow, competition_uow, qm_uow, golf_course_uow).execute(
            player.id
        )

        assert stats.rounds_played == 1
        assert stats.rounds_with_differential == 0
        assert stats.differentials == []
        assert stats.scoring_avg is not None

    async def test_the_two_counters_diverge_when_only_some_rounds_have_a_tee(
        self, user_uow, competition_uow, qm_uow, golf_course_uow
    ):
        """
        El caso que obliga a publicar los dos números: el índice se calcula
        sobre menos vueltas de las que el jugador ha jugado, y sin decirlo
        parecería que las mira todas.
        """
        player = await create_user(user_uow, unique_email("mixed"), handicap=10.0)
        course = await create_golf_course(golf_course_uow, player.id)
        await _played_quick_match(
            qm_uow,
            course,
            player,
            strokes_per_hole=5,
            tee_color=TeeColor.YELLOW,
            tee_gender=Gender.MALE,
        )
        await _played_quick_match(qm_uow, course, player, strokes_per_hole=5)

        stats = await _use_case(user_uow, competition_uow, qm_uow, golf_course_uow).execute(
            player.id
        )

        assert stats.rounds_played == 2
        assert stats.rounds_with_differential == 1

    async def test_no_index_below_three_rounds(
        self, user_uow, competition_uow, qm_uow, golf_course_uow
    ):
        """Dos vueltas dan un número, pero sería ruido con aspecto de dato."""
        player = await create_user(user_uow, unique_email("tworounds"), handicap=10.0)
        course = await create_golf_course(golf_course_uow, player.id)
        for _ in range(2):
            await _played_quick_match(
                qm_uow,
                course,
                player,
                strokes_per_hole=5,
                tee_color=TeeColor.YELLOW,
                tee_gender=Gender.MALE,
            )

        stats = await _use_case(user_uow, competition_uow, qm_uow, golf_course_uow).execute(
            player.id
        )

        assert stats.rounds_with_differential == 2
        assert stats.estimated_index is None
        assert stats.playing_avg == 18.1

    async def test_three_rounds_give_the_best_one_minus_two(
        self, user_uow, competition_uow, qm_uow, golf_course_uow
    ):
        """Tres vueltas de 18.1: la mejor menos el ajuste de la tabla WHS."""
        player = await create_user(user_uow, unique_email("threerounds"), handicap=10.0)
        course = await create_golf_course(golf_course_uow, player.id)
        for _ in range(3):
            await _played_quick_match(
                qm_uow,
                course,
                player,
                strokes_per_hole=5,
                tee_color=TeeColor.YELLOW,
                tee_gender=Gender.MALE,
            )

        stats = await _use_case(user_uow, competition_uow, qm_uow, golf_course_uow).execute(
            player.id
        )

        assert stats.estimated_index == 16.1

    async def test_a_tournament_round_also_yields_a_differential(
        self, user_uow, competition_uow, qm_uow, golf_course_uow
    ):
        """
        El tee de torneo va en el `MatchPlayer`, no en el participante, pero la
        vuelta se mide igual: el formato del partido no cambia lo que dice la
        tarjeta.
        """
        player = await create_user(user_uow, unique_email("tourney"), handicap=10.0)
        rival = await create_user(user_uow, unique_email("rival"), handicap=10.0)
        course = await create_golf_course(golf_course_uow, player.id)
        await _played_competition_match(
            competition_uow, course, player, rival, strokes_per_hole=5
        )

        stats = await _use_case(user_uow, competition_uow, qm_uow, golf_course_uow).execute(
            player.id
        )

        assert stats.differentials == [18.1]

    async def test_differentials_come_newest_first_across_both_sources(
        self, user_uow, competition_uow, qm_uow, golf_course_uow
    ):
        """
        El registro del WHS es cronológico y no distingue de dónde salió cada
        vuelta. La partida rápida se juega hoy; el torneo, en junio.
        """
        player = await create_user(user_uow, unique_email("ordered"), handicap=10.0)
        rival = await create_user(user_uow, unique_email("rival2"), handicap=10.0)
        course = await create_golf_course(golf_course_uow, player.id)
        await _played_competition_match(
            competition_uow,
            course,
            player,
            rival,
            strokes_per_hole=5,
            round_date=date(2026, 6, 1),
        )
        await _played_quick_match(
            qm_uow,
            course,
            player,
            strokes_per_hole=6,
            tee_color=TeeColor.YELLOW,
            tee_gender=Gender.MALE,
        )

        stats = await _use_case(user_uow, competition_uow, qm_uow, golf_course_uow).execute(
            player.id
        )

        # La de hoy (108 golpes -> 34.4) antes que la de junio (90 -> 18.1)
        assert stats.differentials == [34.4, 18.1]
        assert stats.best_differential == 18.1

    async def test_no_trend_without_ten_rounds_to_compare(
        self, user_uow, competition_uow, qm_uow, golf_course_uow
    ):
        """
        Con menos de dos ventanas, la "tendencia" sería la diferencia entre dos
        vueltas sueltas, que es cualquier cosa menos una tendencia.
        """
        player = await create_user(user_uow, unique_email("notrend"), handicap=10.0)
        course = await create_golf_course(golf_course_uow, player.id)
        for _ in range(3):
            await _played_quick_match(
                qm_uow,
                course,
                player,
                strokes_per_hole=5,
                tee_color=TeeColor.YELLOW,
                tee_gender=Gender.MALE,
            )

        stats = await _use_case(user_uow, competition_uow, qm_uow, golf_course_uow).execute(
            player.id
        )

        assert stats.handicap_trend is None

    async def test_a_player_with_no_rounds_gets_nulls_and_empty_series(
        self, user_uow, competition_uow, qm_uow, golf_course_uow
    ):
        """Nada que enseñar no es un cero: son huecos, y se dicen como tales."""
        player = await create_user(user_uow, unique_email("empty"), handicap=10.0)
        await create_golf_course(golf_course_uow, player.id)

        stats = await _use_case(user_uow, competition_uow, qm_uow, golf_course_uow).execute(
            player.id
        )

        assert stats.estimated_index is None
        assert stats.playing_avg is None
        assert stats.best_differential is None
        assert stats.handicap_trend is None
        assert stats.differentials == []
        assert stats.rounds_with_differential == 0

    async def test_the_course_filter_also_narrows_the_differentials(
        self, user_uow, competition_uow, qm_uow, golf_course_uow
    ):
        """
        El desglose por campo tiene que ser coherente consigo mismo: si la
        vuelta no entra en la media de ese campo, tampoco en su índice.
        """
        player = await create_user(user_uow, unique_email("bycourse"), handicap=10.0)
        course = await create_golf_course(golf_course_uow, player.id)
        other_course = await create_golf_course(golf_course_uow, player.id)
        await _played_quick_match(
            qm_uow,
            course,
            player,
            strokes_per_hole=5,
            tee_color=TeeColor.YELLOW,
            tee_gender=Gender.MALE,
        )
        await _played_quick_match(
            qm_uow,
            other_course,
            player,
            strokes_per_hole=8,
            tee_color=TeeColor.YELLOW,
            tee_gender=Gender.MALE,
        )

        stats = await _use_case(user_uow, competition_uow, qm_uow, golf_course_uow).execute(
            player.id, golf_course_id=course.id
        )

        assert stats.differentials == [18.1]


class TestScoringRecordWindow:
    """
    La serie publicada y las cifras calculadas hablan de las mismas vueltas.

    Sin esto, un cliente que sacara el mínimo de `differentials` por su cuenta
    obtendría un número que no coincide con `best_differential`.
    """

    async def test_the_series_is_capped_at_the_twenty_round_record(
        self, user_uow, competition_uow, qm_uow, golf_course_uow
    ):
        player = await create_user(user_uow, unique_email("window"), handicap=10.0)
        course = await create_golf_course(golf_course_uow, player.id)
        for _ in range(21):
            await _played_quick_match(
                qm_uow,
                course,
                player,
                strokes_per_hole=5,
                tee_color=TeeColor.YELLOW,
                tee_gender=Gender.MALE,
            )

        stats = await _use_case(user_uow, competition_uow, qm_uow, golf_course_uow).execute(
            player.id
        )

        # Las 21 se cuentan y se promedian, pero solo 20 se publican
        assert stats.rounds_played == 21
        assert stats.rounds_with_differential == 21
        assert len(stats.differentials) == 20
        assert min(stats.differentials) == stats.best_differential


class TestParPorBarra:
    """
    La media se mide contra el par de la barra jugada.

    En 25 de los 800 campos federados el par cambia de una barra a otra. Medir
    a todos contra la tarjeta de referencia le cuenta a quien juega otra barra
    una vuelta mejor o peor de la que hizo.
    """

    @staticmethod
    async def _course_with_longer_red(golf_course_uow, creator_id):
        """Rojas juegan par 5 los hoyos 1 y 2 (par 74); el campo, par 72."""
        tees = [
            Tee(
                color=TeeColor.YELLOW,
                gender=Gender.MALE,
                identifier="Yellow",
                course_rating=70.0,
                slope_rating=125,
                holes=[Hole(number=i, par=4, stroke_index=i) for i in range(1, 19)],
            ),
            Tee(
                color=TeeColor.RED,
                gender=Gender.FEMALE,
                identifier="Red",
                course_rating=72.0,
                slope_rating=130,
                holes=[
                    Hole(number=i, par=5 if i in (1, 2) else 4, stroke_index=i)
                    for i in range(1, 19)
                ],
            ),
        ]
        course = GolfCourse.create(
            name="Two Cards Club",
            country_code=CountryCode("ES"),
            course_type=CourseType.STANDARD_18,
            creator_id=creator_id,
            tees=tees,
            holes=[Hole(number=i, par=4, stroke_index=i) for i in range(1, 19)],
        )
        course.approve()
        async with golf_course_uow:
            await golf_course_uow.golf_courses.save(course)
        return course

    @pytest.mark.asyncio
    async def test_la_media_va_contra_el_par_de_su_barra(
        self, user_uow, competition_uow, qm_uow, golf_course_uow
    ):
        """
        Scratch de rojas (par 74) firmando 4 en todos los hoyos: 72 golpes,
        dos bajo su par. Contra la tarjeta del campo (par 72) daría 0, que es
        lo que salía antes.
        """
        user = await create_user(user_uow, unique_email("red"), handicap=0)
        course = await self._course_with_longer_red(golf_course_uow, user.id)
        await _played_quick_match(
            qm_uow,
            course,
            user,
            strokes_per_hole=4,
            tee_color=TeeColor.RED,
            tee_gender=Gender.FEMALE,
        )

        stats = await _use_case(user_uow, competition_uow, qm_uow, golf_course_uow).execute(
            user.id
        )

        assert stats.scoring_avg == -2.0

    @pytest.mark.asyncio
    async def test_la_base_de_golpes_sale_del_par_de_su_barra(
        self, user_uow, competition_uow, qm_uow, golf_course_uow
    ):
        """
        El par entra en el Course Handicap como `(CR - Par)`, así que con el par
        del campo el jugador de otra barra recibe golpes de más y su tope de
        doble bogey neto sube: el diferencial sale mejor de lo que jugó.

        Índice 10 desde rojas (par 74, CR 72, SR 130): 10 x 130/113 - 2 = 9.5,
        que redondea a 10 golpes. Con el par del campo serían 11.5 -> 12, dos
        golpes de más, y el desastre del hoyo con índice 11 se topa un golpe más
        arriba.
        """
        user = await create_user(user_uow, unique_email("base"), handicap=10)
        course = await self._course_with_longer_red(golf_course_uow, user.id)
        tarjeta = dict.fromkeys(range(1, 19), 4)
        tarjeta[11] = 9  # el hoyo de stroke index 11, donde cambia el reparto
        await _played_quick_match(
            qm_uow,
            course,
            user,
            holes=list(range(1, 19)),
            tee_color=TeeColor.RED,
            tee_gender=Gender.FEMALE,
            scores_by_hole=tarjeta,
        )

        stats = await _use_case(user_uow, competition_uow, qm_uow, golf_course_uow).execute(
            user.id
        )

        assert stats.best_differential == 1.7

    @pytest.mark.asyncio
    async def test_una_barra_con_par_fuera_de_rango_no_borra_la_vuelta(
        self, user_uow, competition_uow, qm_uow, golf_course_uow
    ):
        """
        `TeeRating` rechaza el par fuera de 66-76, y valorar la barra por su
        propio par metió ese rechazo donde antes no llegaba: la vuelta se
        quedaba sin rating, sin diferencial y desaparecía de las estadísticas.
        Un dato suelto del importador no puede borrar una vuelta que sí se
        jugó, así que se valora contra el par del campo.
        """
        user = await create_user(user_uow, unique_email("short"), handicap=10)
        referencia = [Hole(number=i, par=4 if i <= 13 else 3, stroke_index=i) for i in range(1, 19)]
        roja = [Hole(number=i, par=4 if i <= 11 else 3, stroke_index=i) for i in range(1, 19)]
        assert sum(h.par for h in roja) == 65  # fuera del rango WHS, a propósito

        course = GolfCourse.create(
            name="Short Course",
            country_code=CountryCode("ES"),
            course_type=CourseType.STANDARD_18,
            creator_id=user.id,
            tees=[
                Tee(
                    color=TeeColor.YELLOW,
                    gender=Gender.MALE,
                    identifier="Yellow",
                    course_rating=67.0,
                    slope_rating=113,
                    holes=referencia,
                ),
                Tee(
                    color=TeeColor.RED,
                    gender=Gender.FEMALE,
                    identifier="Red",
                    course_rating=66.0,
                    slope_rating=110,
                    holes=roja,
                ),
            ],
            holes=referencia,
        )
        course.approve()
        async with golf_course_uow:
            await golf_course_uow.golf_courses.save(course)

        await _played_quick_match(
            qm_uow,
            course,
            user,
            strokes_per_hole=4,
            tee_color=TeeColor.RED,
            tee_gender=Gender.FEMALE,
        )

        stats = await _use_case(user_uow, competition_uow, qm_uow, golf_course_uow).execute(
            user.id
        )

        assert stats.rounds_with_differential == 1
        assert stats.best_differential is not None
