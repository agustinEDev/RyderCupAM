"""
Tests de integración de `find_completed_for_player` (BE #128).

Esta consulta no se puede verificar de verdad en memoria: busca al jugador con
contención JSONB (`@>`) sobre dos columnas sin clave ajena, y ordena por la
fecha de la ronda, que vive en otra tabla. La implementación en memoria ordena
por `created_at` a falta de rondas, así que el orden real solo se comprueba
aquí, contra PostgreSQL.
"""

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import text

from src.modules.competition.domain.entities.competition import Competition
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
from src.modules.competition.infrastructure.persistence.sqlalchemy.competition_repository import (
    SQLAlchemyCompetitionRepository,
)
from src.modules.competition.infrastructure.persistence.sqlalchemy.match_repository import (
    SQLAlchemyMatchRepository,
)
from src.modules.competition.infrastructure.persistence.sqlalchemy.round_repository import (
    SQLAlchemyRoundRepository,
)
from src.modules.golf_course.domain.entities.golf_course import GolfCourse
from src.modules.golf_course.domain.entities.hole import Hole
from src.modules.golf_course.domain.entities.tee import Tee
from src.modules.golf_course.domain.value_objects.course_type import CourseType
from src.modules.golf_course.domain.value_objects.tee_category import TeeCategory
from src.modules.golf_course.infrastructure.persistence.repositories.golf_course_repository import (
    GolfCourseRepository,
)
from src.modules.user.domain.value_objects.user_id import UserId
from src.shared.domain.value_objects.country_code import CountryCode
from src.shared.domain.value_objects.gender import Gender

pytestmark = [pytest.mark.integration]

BASE_DATE = date(2026, 6, 1)


async def _insert_user(db_session, user_id: UserId) -> None:
    """Fila mínima de usuario: las claves ajenas de competitions la exigen."""
    now = datetime.now(UTC).replace(tzinfo=None)
    await db_session.execute(
        text(
            "INSERT INTO users (id, first_name, last_name, email, password, "
            "created_at, updated_at, email_verified, failed_login_attempts, is_admin) "
            "VALUES (:id, :fn, :ln, :email, :pw, :ca, :ua, :ev, :fla, :ia)"
        ),
        {
            "id": str(user_id.value),
            "fn": "Test",
            "ln": "Player",
            "email": f"match-history-{user_id.value}@example.com",
            "pw": "$2b$04$placeholder",
            "ca": now,
            "ua": now,
            "ev": False,
            "fla": 0,
            "ia": False,
        },
    )


@pytest_asyncio.fixture
async def player_id(db_session) -> UserId:
    user_id = UserId.generate()
    await _insert_user(db_session, user_id)
    return user_id


@pytest_asyncio.fixture
async def rival_id(db_session) -> UserId:
    user_id = UserId.generate()
    await _insert_user(db_session, user_id)
    return user_id


@pytest_asyncio.fixture
async def golf_course_id(db_session, player_id) -> object:
    course = GolfCourse.create(
        name=f"History Club {uuid4().hex[:6]}",
        country_code=CountryCode("ES"),
        course_type=CourseType.STANDARD_18,
        creator_id=player_id,
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
        holes=[Hole(number=i, par=4, stroke_index=i) for i in range(1, 19)],
    )
    course.approve()
    await GolfCourseRepository(db_session).save(course)
    await db_session.commit()
    return course.id


async def _create_competition(db_session, creator_id) -> Competition:
    competition = Competition.create(
        id=CompetitionId(uuid4()),
        creator_id=creator_id,
        name=CompetitionName(f"History Cup {uuid4().hex[:6]}"),
        dates=DateRange(start_date=BASE_DATE, end_date=BASE_DATE + timedelta(days=5)),
        location=Location(main_country=CountryCode("ES")),
        play_mode=PlayMode.SCRATCH,
        team_1_name="Team A",
        team_2_name="Team B",
    )
    await SQLAlchemyCompetitionRepository(db_session).add(competition)
    await db_session.commit()
    return competition


async def _create_round(db_session, competition, golf_course_id, round_date: date) -> Round:
    round_ = Round.create(
        competition_id=competition.id,
        golf_course_id=golf_course_id,
        round_date=round_date,
        session_type=SessionType.MORNING,
        match_format=MatchFormat.SINGLES,
    )
    await SQLAlchemyRoundRepository(db_session).add(round_)
    await db_session.commit()
    return round_


def _player(user_id: UserId) -> MatchPlayer:
    return MatchPlayer(
        user_id=user_id,
        playing_handicap=10,
        tee_category=TeeCategory.AMATEUR,
        tee_gender=Gender.MALE,
        strokes_received=tuple(range(1, 11)),
        player_handicap=Decimal("10.0"),
    )


async def _create_match(
    db_session,
    round_: Round,
    team_a: list[UserId],
    team_b: list[UserId],
    *,
    completed: bool = True,
    match_number: int = 1,
) -> Match:
    match = Match.create(
        round_id=round_.id,
        match_number=match_number,
        team_a_players=[_player(uid) for uid in team_a],
        team_b_players=[_player(uid) for uid in team_b],
    )
    if completed:
        match.start()
        match.complete({"winner": "A", "score": "3&2"})

    await SQLAlchemyMatchRepository(db_session).add(match)
    await db_session.commit()
    return match


async def test_finds_a_completed_match_where_the_player_is_in_team_a(
    db_session, player_id, rival_id, golf_course_id
):
    competition = await _create_competition(db_session, player_id)
    round_ = await _create_round(db_session, competition, golf_course_id, BASE_DATE)
    match = await _create_match(db_session, round_, [player_id], [rival_id])

    found = await SQLAlchemyMatchRepository(db_session).find_completed_for_player(player_id)

    assert [m.id for m in found] == [match.id]


async def test_finds_the_same_match_from_the_other_side_of_the_draw(
    db_session, player_id, rival_id, golf_course_id
):
    """Los jugadores viven en dos columnas JSONB distintas: hay que mirar en las dos."""
    competition = await _create_competition(db_session, player_id)
    round_ = await _create_round(db_session, competition, golf_course_id, BASE_DATE)
    match = await _create_match(db_session, round_, [player_id], [rival_id])

    found = await SQLAlchemyMatchRepository(db_session).find_completed_for_player(rival_id)

    assert [m.id for m in found] == [match.id]


async def test_ignores_matches_the_player_did_not_play(
    db_session, player_id, rival_id, golf_course_id
):
    """La contención JSONB no puede colar partidos ajenos del mismo torneo."""
    outsider_id = UserId.generate()
    await _insert_user(db_session, outsider_id)
    competition = await _create_competition(db_session, player_id)
    round_ = await _create_round(db_session, competition, golf_course_id, BASE_DATE)
    await _create_match(db_session, round_, [player_id], [rival_id])

    found = await SQLAlchemyMatchRepository(db_session).find_completed_for_player(outsider_id)

    assert found == []


async def test_ignores_matches_that_have_not_finished(
    db_session, player_id, rival_id, golf_course_id
):
    """Un partido a medias todavía no dice cómo quedó: no es historial."""
    competition = await _create_competition(db_session, player_id)
    round_ = await _create_round(db_session, competition, golf_course_id, BASE_DATE)
    await _create_match(db_session, round_, [player_id], [rival_id], completed=False)

    found = await SQLAlchemyMatchRepository(db_session).find_completed_for_player(player_id)

    assert found == []


async def test_orders_by_round_date_most_recent_first(
    db_session, player_id, rival_id, golf_course_id
):
    """
    El orden sale de la fecha de la ronda, no de cuándo se creó la fila: los
    partidos se crean al planificar el torneo, en el orden que quiera el creador.
    """
    competition = await _create_competition(db_session, player_id)
    early_round = await _create_round(db_session, competition, golf_course_id, BASE_DATE)
    late_round = await _create_round(
        db_session, competition, golf_course_id, BASE_DATE + timedelta(days=2)
    )
    # Se crea antes el de la ronda temprana, para que el orden por fecha no
    # coincida con el orden de inserción
    early_match = await _create_match(db_session, early_round, [player_id], [rival_id])
    late_match = await _create_match(db_session, late_round, [player_id], [rival_id])

    found = await SQLAlchemyMatchRepository(db_session).find_completed_for_player(player_id)

    assert [m.id for m in found] == [late_match.id, early_match.id]


async def test_limit_keeps_the_most_recent_ones(db_session, player_id, rival_id, golf_course_id):
    competition = await _create_competition(db_session, player_id)
    early_round = await _create_round(db_session, competition, golf_course_id, BASE_DATE)
    late_round = await _create_round(
        db_session, competition, golf_course_id, BASE_DATE + timedelta(days=2)
    )
    await _create_match(db_session, early_round, [player_id], [rival_id])
    late_match = await _create_match(db_session, late_round, [player_id], [rival_id])

    found = await SQLAlchemyMatchRepository(db_session).find_completed_for_player(
        player_id, limit=1
    )

    assert [m.id for m in found] == [late_match.id]
