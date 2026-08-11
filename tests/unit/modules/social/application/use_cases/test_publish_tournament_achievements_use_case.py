"""
Tests de la publicacion de logros de un torneo (BE #175).

Un torneo son varias vueltas por jugador, y eso trae dos reglas propias: cada
partido lleva su propio `source_match_id`, y `FIRST_TOURNAMENT` se publica una
sola vez aunque el jugador haya jugado cuatro partidos.
"""

from datetime import date, timedelta
from uuid import uuid4

import pytest

from src.modules.competition.domain.entities.competition import Competition
from src.modules.competition.domain.entities.enrollment import Enrollment
from src.modules.competition.domain.entities.hole_score import HoleScore
from src.modules.competition.domain.entities.match import Match
from src.modules.competition.domain.entities.round import Round
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.competition_name import CompetitionName
from src.modules.competition.domain.value_objects.date_range import DateRange
from src.modules.competition.domain.value_objects.enrollment_id import EnrollmentId
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
from src.modules.social.application.ports.player_course_history_interface import (
    PlayerCourseHistoryInterface,
)
from src.modules.social.application.ports.player_differentials_interface import (
    PlayerDifferentialsInterface,
)
from src.modules.social.application.use_cases.publish_tournament_achievements_use_case import (
    PublishTournamentAchievementsUseCase,
)
from src.modules.social.domain.value_objects.activity_event_type import ActivityEventType
from src.modules.social.infrastructure.persistence.in_memory.in_memory_social_unit_of_work import (
    InMemorySocialUnitOfWork,
)
from src.modules.user.domain.entities.user import User
from src.modules.user.infrastructure.persistence.in_memory.in_memory_unit_of_work import (
    InMemoryUnitOfWork as InMemoryUserUnitOfWork,
)
from src.shared.domain.value_objects.country_code import CountryCode
from src.shared.domain.value_objects.gender import Gender

pytestmark = pytest.mark.asyncio

PAR = 4
ROUND_DATE = date(2026, 6, 1)


class _DifferentialsStub(PlayerDifferentialsInterface):
    def __init__(self, por_jugador: dict | None = None):
        self._por_jugador = por_jugador or {}

    async def best_differential(self, user_id):
        return self._por_jugador.get(str(user_id.value))


class _CourseHistoryFake(PlayerCourseHistoryInterface):
    """Sin historial previo: todo campo se estrena, salvo lo que se registre."""

    def __init__(self):
        self._vueltas: set = set()

    def registra(self, user_id, golf_course_id: str, match_id: str) -> None:
        self._vueltas.add((str(user_id.value), golf_course_id, match_id))

    async def has_played_course_before(
        self, user_id, golf_course_id: str, excluding_match_id: str
    ) -> bool:
        return any(
            usuario == str(user_id.value)
            and campo == golf_course_id
            and partida != excluding_match_id
            for usuario, campo, partida in self._vueltas
        )


@pytest.fixture
def competition_uow():
    return InMemoryCompetitionUnitOfWork()


@pytest.fixture
def golf_course_uow():
    return InMemoryGolfCourseUnitOfWork()


@pytest.fixture
def user_uow():
    return InMemoryUserUnitOfWork()


@pytest.fixture
def social_uow():
    return InMemorySocialUnitOfWork()


async def _create_user(user_uow, share_activity: bool = True) -> User:
    user = User.create(
        first_name="Test",
        last_name="User",
        email_str=f"tfeed_{uuid4().hex[:8]}@test.com",
        plain_password="SecureP@ssw0rd123",
    )
    if not share_activity:
        user.set_activity_sharing(False)
    async with user_uow:
        await user_uow.users.save(user)
    return user


async def _create_course(golf_course_uow, creator_id):
    course = GolfCourse.create(
        name="Tournament Golf Club",
        country_code=CountryCode("ES"),
        course_type=CourseType.STANDARD_18,
        creator_id=creator_id,
        tees=[
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
        ],
        holes=[Hole(number=i, par=PAR, stroke_index=i) for i in range(1, 19)],
    )
    course.approve()
    async with golf_course_uow:
        await golf_course_uow.golf_courses.save(course)
    return course


async def _completed_tournament(
    competition_uow,
    course,
    player,
    rival,
    *,
    scores_by_hole: dict | None = None,
    matches: int = 1,
    round_date: date = ROUND_DATE,
    complete: bool = True,
):
    """Un torneo terminado con la tarjeta del jugador anotada en cada partido."""
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
    if complete:
        competition.activate()
        competition.close_enrollments(total_enrollments=2)
        competition.start()
        competition.complete()

    round_ = Round.create(
        competition_id=competition.id,
        golf_course_id=course.id,
        round_date=round_date,
        session_type=SessionType.MORNING,
        match_format=MatchFormat.SINGLES,
    )

    def match_player(user_id):
        return MatchPlayer(
            user_id=user_id,
            playing_handicap=0,
            tee_category=TeeCategory.AMATEUR,
            tee_gender=Gender.MALE,
            # Scratch: no recibe golpe en ningun hoyo
            strokes_received=(),
        )

    tarjeta = scores_by_hole or dict.fromkeys(range(1, 19), PAR)
    creados = []

    async with competition_uow:
        await competition_uow.competitions.add(competition)
        await competition_uow.rounds.add(round_)
        for numero in range(1, matches + 1):
            match = Match.create(
                round_id=round_.id,
                match_number=numero,
                team_a_players=[match_player(player.id)],
                team_b_players=[match_player(rival.id)],
            )
            match.start()
            match.complete({"winner": "A", "score": "2UP"})
            await competition_uow.matches.add(match)
            for hole_number, strokes in tarjeta.items():
                hole_score = HoleScore.create(
                    match_id=match.id,
                    hole_number=hole_number,
                    player_user_id=player.id,
                    team="A",
                    strokes_received=0,
                )
                hole_score.set_own_score(strokes)
                await competition_uow.hole_scores.add(hole_score)
            creados.append(match)

        for jugador in (player, rival):
            await competition_uow.enrollments.add(
                Enrollment.direct_enroll(
                    id=EnrollmentId(uuid4()),
                    competition_id=competition.id,
                    user_id=jugador.id,
                )
            )
        await competition_uow.commit()

    return competition, creados


def _use_case(
    social_uow, competition_uow, golf_course_uow, user_uow, differentials=None, history=None
):
    return PublishTournamentAchievementsUseCase(
        social_uow=social_uow,
        competition_uow=competition_uow,
        golf_course_uow=golf_course_uow,
        user_uow=user_uow,
        differentials=differentials or _DifferentialsStub(),
        history=history or _CourseHistoryFake(),
    )


async def _feed_de(social_uow, user):
    async with social_uow:
        return await social_uow.activity_events.find_for_users([user.id], limit=50)


async def test_publica_los_logros_de_la_vuelta_de_torneo(
    social_uow, competition_uow, golf_course_uow, user_uow
):
    """Given un torneo con un birdie / When se cierra / Then sale en el feed."""
    player = await _create_user(user_uow)
    rival = await _create_user(user_uow)
    course = await _create_course(golf_course_uow, player.id)
    tarjeta = dict.fromkeys(range(1, 19), PAR)
    tarjeta[4] = PAR - 1
    competition, _ = await _completed_tournament(
        competition_uow, course, player, rival, scores_by_hole=tarjeta
    )

    await _use_case(social_uow, competition_uow, golf_course_uow, user_uow).execute(
        str(competition.id.value)
    )

    eventos = await _feed_de(social_uow, player)
    birdies = [e for e in eventos if e.type == ActivityEventType.BIRDIE]
    assert len(birdies) == 1
    assert birdies[0].payload["from_tournament"] is True


async def test_el_primer_torneo_se_publica_una_sola_vez(
    social_uow, competition_uow, golf_course_uow, user_uow
):
    """
    Given un jugador que estrena torneo jugando tres partidos / When se cierra /
    Then la noticia sale una vez, no tres.
    """
    player = await _create_user(user_uow)
    rival = await _create_user(user_uow)
    course = await _create_course(golf_course_uow, player.id)
    competition, _ = await _completed_tournament(
        competition_uow, course, player, rival, matches=3
    )

    await _use_case(social_uow, competition_uow, golf_course_uow, user_uow).execute(
        str(competition.id.value)
    )

    estrenos = [
        e
        for e in await _feed_de(social_uow, player)
        if e.type == ActivityEventType.FIRST_TOURNAMENT
    ]
    assert len(estrenos) == 1


async def test_cada_partido_lleva_su_propia_entrada(
    social_uow, competition_uow, golf_course_uow, user_uow
):
    """
    Given dos partidos con birdie / When se cierra el torneo / Then hay una
    entrada de birdie por partido, cada una colgada del suyo.
    """
    player = await _create_user(user_uow)
    rival = await _create_user(user_uow)
    course = await _create_course(golf_course_uow, player.id)
    tarjeta = dict.fromkeys(range(1, 19), PAR)
    tarjeta[4] = PAR - 1
    competition, partidos = await _completed_tournament(
        competition_uow, course, player, rival, scores_by_hole=tarjeta, matches=2
    )

    await _use_case(social_uow, competition_uow, golf_course_uow, user_uow).execute(
        str(competition.id.value)
    )

    birdies = [
        e for e in await _feed_de(social_uow, player) if e.type == ActivityEventType.BIRDIE
    ]
    assert len(birdies) == 2
    assert {e.source_match_id for e in birdies} == {str(p.id.value) for p in partidos}


async def test_reprocesar_el_cierre_no_duplica(
    social_uow, competition_uow, golf_course_uow, user_uow
):
    """Given un torneo ya publicado / When se reprocesa / Then el feed no crece."""
    player = await _create_user(user_uow)
    rival = await _create_user(user_uow)
    course = await _create_course(golf_course_uow, player.id)
    competition, _ = await _completed_tournament(competition_uow, course, player, rival)
    use_case = _use_case(social_uow, competition_uow, golf_course_uow, user_uow)

    await use_case.execute(str(competition.id.value))
    antes = len(await _feed_de(social_uow, player))
    await use_case.execute(str(competition.id.value))

    assert len(await _feed_de(social_uow, player)) == antes


async def test_no_publica_de_quien_lo_tiene_apagado(
    social_uow, competition_uow, golf_course_uow, user_uow
):
    """Given un inscrito con la publicacion apagada / When se cierra / Then no aparece."""
    player = await _create_user(user_uow, share_activity=False)
    rival = await _create_user(user_uow)
    course = await _create_course(golf_course_uow, player.id)
    competition, _ = await _completed_tournament(competition_uow, course, player, rival)

    await _use_case(social_uow, competition_uow, golf_course_uow, user_uow).execute(
        str(competition.id.value)
    )

    assert await _feed_de(social_uow, player) == []


async def test_un_torneo_sin_cerrar_no_publica(
    social_uow, competition_uow, golf_course_uow, user_uow
):
    """Given un torneo en juego / When se intenta publicar / Then no publica nada."""
    player = await _create_user(user_uow)
    rival = await _create_user(user_uow)
    course = await _create_course(golf_course_uow, player.id)
    competition, _ = await _completed_tournament(
        competition_uow, course, player, rival, complete=False
    )

    publicados = await _use_case(
        social_uow, competition_uow, golf_course_uow, user_uow
    ).execute(str(competition.id.value))

    assert publicados == 0


async def test_una_tarjeta_incompleta_no_llega_al_feed(
    social_uow, competition_uow, golf_course_uow, user_uow
):
    """Given una tarjeta con huecos / When se cierra / Then esa vuelta no cuenta."""
    player = await _create_user(user_uow)
    rival = await _create_user(user_uow)
    course = await _create_course(golf_course_uow, player.id)
    tarjeta = dict.fromkeys(range(1, 13), PAR)
    tarjeta[4] = PAR - 1
    competition, _ = await _completed_tournament(
        competition_uow, course, player, rival, scores_by_hole=tarjeta
    )

    publicados = await _use_case(
        social_uow, competition_uow, golf_course_uow, user_uow
    ).execute(str(competition.id.value))

    assert publicados == 0


async def test_un_torneo_que_no_existe_no_rompe(
    social_uow, competition_uow, golf_course_uow, user_uow
):
    """Given un id que no existe / When se publica / Then devuelve cero sin fallar."""
    publicados = await _use_case(
        social_uow, competition_uow, golf_course_uow, user_uow
    ).execute(str(uuid4()))

    assert publicados == 0
