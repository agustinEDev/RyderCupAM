"""
Tests de integración de `find_by_id_for_update` (BE #305).

La apertura automática de la anotación se protege releyendo el partido con su
fila bloqueada: dos jugadores pueden mandar su primer golpe a la vez, y abrirlo
dos veces duplicaría los 18 hoyos de cada uno, que `add_many` no deduplica.

Eso **no se puede comprobar en memoria**: allí el repositorio devuelve el mismo
objeto y siempre está al día. Contra PostgreSQL, en cambio, si la relectura no
fuerza el refresco, SQLAlchemy devuelve el objeto que ya tiene en su mapa de
identidad —con el estado viejo— y la guarda no se dispara nunca.
"""

from datetime import UTC, date, datetime, timedelta
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
from src.modules.competition.domain.value_objects.match_status import MatchStatus
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
from src.modules.golf_course.domain.value_objects.tee_color import TeeColor
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
            "email": f"for-update-{user_id.value}@example.com",
            "pw": "$2b$04$placeholder",
            "ca": now,
            "ua": now,
            "ev": False,
            "fla": 0,
            "ia": False,
        },
    )


@pytest_asyncio.fixture
async def creator_id(db_session) -> UserId:
    user_id = UserId.generate()
    await _insert_user(db_session, user_id)
    return user_id


@pytest_asyncio.fixture
async def golf_course_id(db_session, creator_id) -> object:
    course = GolfCourse.create(
        name=f"Lock Club {uuid4().hex[:6]}",
        country_code=CountryCode("ES"),
        course_type=CourseType.STANDARD_18,
        creator_id=creator_id,
        tees=[
            Tee(
                color=TeeColor.YELLOW,
                gender=Gender.MALE,
                identifier="Yellow",
                course_rating=70.0,
                slope_rating=125,
            ),
        ],
        holes=[Hole(number=i, par=4, stroke_index=i) for i in range(1, 19)],
    )
    course.approve()
    await GolfCourseRepository(db_session).save(course)
    await db_session.commit()
    return course.id


@pytest_asyncio.fixture
async def match(db_session, creator_id, golf_course_id) -> Match:
    competition = Competition.create(
        id=CompetitionId(uuid4()),
        creator_id=creator_id,
        name=CompetitionName(f"Lock Cup {uuid4().hex[:6]}"),
        dates=DateRange(start_date=BASE_DATE, end_date=BASE_DATE + timedelta(days=2)),
        location=Location(main_country=CountryCode("ES")),
        play_mode=PlayMode.SCRATCH,
        team_1_name="Team A",
        team_2_name="Team B",
    )
    await SQLAlchemyCompetitionRepository(db_session).add(competition)
    await db_session.commit()

    round_ = Round.create(
        competition_id=competition.id,
        golf_course_id=golf_course_id,
        round_date=BASE_DATE,
        session_type=SessionType.MORNING,
        match_format=MatchFormat.SINGLES,
    )
    await SQLAlchemyRoundRepository(db_session).add(round_)
    await db_session.commit()

    jugador = MatchPlayer.create(
        user_id=creator_id,
        playing_handicap=0,
        tee_color=TeeColor.YELLOW,
        strokes_received=[],
        tee_gender=Gender.MALE,
    )
    partido = Match.create(
        round_id=round_.id,
        match_number=1,
        team_a_players=[jugador],
        team_b_players=[jugador],
    )
    await SQLAlchemyMatchRepository(db_session).add(partido)
    await db_session.commit()
    return partido


class TestFindByIdForUpdate:
    @pytest.mark.asyncio
    async def test_devuelve_el_estado_de_la_base_de_datos_no_el_que_ya_tenia(
        self, db_session, match
    ):
        """
        Otro proceso abrió el partido después de que yo lo leyera.

        Sin refrescar, SQLAlchemy devuelve el objeto de su mapa de identidad
        —todavía SCHEDULED— y la apertura automática lo abriría por segunda vez,
        duplicando los hoyos de cada jugador.
        """
        repo = SQLAlchemyMatchRepository(db_session)

        leido = await repo.find_by_id(match.id)
        assert leido.status == MatchStatus.SCHEDULED

        # Otro proceso lo abre y confirma
        await db_session.execute(
            text("UPDATE matches SET status = 'IN_PROGRESS' WHERE id = :id"),
            {"id": str(match.id.value)},
        )
        await db_session.commit()

        bloqueado = await repo.find_by_id_for_update(match.id)

        assert bloqueado is not None
        assert bloqueado.status == MatchStatus.IN_PROGRESS

    @pytest.mark.asyncio
    async def test_un_partido_que_no_existe_devuelve_none(self, db_session, match):
        from src.modules.competition.domain.value_objects.match_id import MatchId

        assert await SQLAlchemyMatchRepository(db_session).find_by_id_for_update(
            MatchId(uuid4())
        ) is None
