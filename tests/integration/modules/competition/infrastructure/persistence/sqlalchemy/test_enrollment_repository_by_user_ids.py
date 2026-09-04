"""
Tests de integración de `find_by_user_ids_and_competition` (BE #254).

Esta consulta liga la preferencia de nombre de cada jugador con la
clasificación en producción, y ata en corto el `.in_()` de SQLAlchemy contra
el `UserIdDecorator` del módulo: en memoria ese enlace no se ejercita —el
repositorio en memoria compara objetos Python directamente—, así que solo
aquí, contra PostgreSQL, se comprueba que la conversión funciona de verdad.
"""

from datetime import UTC, date, datetime, timedelta
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import text

from src.modules.competition.domain.entities.competition import Competition
from src.modules.competition.domain.entities.enrollment import Enrollment
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.competition_name import CompetitionName
from src.modules.competition.domain.value_objects.date_range import DateRange
from src.modules.competition.domain.value_objects.enrollment_id import EnrollmentId
from src.modules.competition.domain.value_objects.location import Location
from src.modules.competition.domain.value_objects.play_mode import PlayMode
from src.modules.competition.infrastructure.persistence.sqlalchemy.competition_repository import (
    SQLAlchemyCompetitionRepository,
)
from src.modules.competition.infrastructure.persistence.sqlalchemy.enrollment_repository import (
    SQLAlchemyEnrollmentRepository,
)
from src.modules.user.domain.value_objects.user_id import UserId
from src.shared.domain.value_objects.country_code import CountryCode

pytestmark = [pytest.mark.integration]

BASE_DATE = date(2026, 6, 1)


async def _insert_user(db_session, user_id: UserId) -> None:
    """Fila mínima de usuario: las claves ajenas de enrollments la exigen."""
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
            "email": f"enrollment-by-ids-{user_id.value}@example.com",
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
async def competition_id(db_session, creator_id) -> CompetitionId:
    competition = Competition.create(
        id=CompetitionId(uuid4()),
        creator_id=creator_id,
        name=CompetitionName(f"Name Preference Cup {uuid4().hex[:6]}"),
        dates=DateRange(start_date=BASE_DATE, end_date=BASE_DATE + timedelta(days=5)),
        location=Location(main_country=CountryCode("ES")),
        play_mode=PlayMode.SCRATCH,
        team_1_name="Team A",
        team_2_name="Team B",
    )
    await SQLAlchemyCompetitionRepository(db_session).add(competition)
    await db_session.commit()
    return competition.id


async def _enroll(db_session, competition_id: CompetitionId, user_id: UserId, use_real_name: bool):
    enrollment = Enrollment.direct_enroll(
        id=EnrollmentId.generate(), competition_id=competition_id, user_id=user_id
    )
    enrollment.set_name_preference(use_real_name)
    repo = SQLAlchemyEnrollmentRepository(db_session)
    await repo.add(enrollment)
    await db_session.commit()
    return enrollment


class TestFindByUserIdsAndCompetition:
    async def test_returns_only_the_enrollments_of_the_requested_users(
        self, db_session, competition_id
    ):
        """
        Dos jugadores inscritos, uno con nombre real y otro con alias; un
        tercero ajeno a la lista de `user_ids` pedida. Solo vuelven los dos
        primeros, cada uno con su preferencia intacta.
        """
        wanted_a = UserId.generate()
        await _insert_user(db_session, wanted_a)
        wanted_b = UserId.generate()
        await _insert_user(db_session, wanted_b)
        not_wanted = UserId.generate()
        await _insert_user(db_session, not_wanted)

        await _enroll(db_session, competition_id, wanted_a, use_real_name=True)
        await _enroll(db_session, competition_id, wanted_b, use_real_name=False)
        await _enroll(db_session, competition_id, not_wanted, use_real_name=True)

        repo = SQLAlchemyEnrollmentRepository(db_session)
        found = await repo.find_by_user_ids_and_competition(
            [wanted_a, wanted_b], competition_id
        )

        by_user = {e.user_id: e for e in found}
        assert set(by_user) == {wanted_a, wanted_b}
        assert by_user[wanted_a].use_real_name is True
        assert by_user[wanted_b].use_real_name is False

    async def test_returns_empty_list_for_an_empty_user_id_list(self, db_session, competition_id):
        """Sin `user_ids` no hay nada que pedir: ni una consulta de más."""
        repo = SQLAlchemyEnrollmentRepository(db_session)

        found = await repo.find_by_user_ids_and_competition([], competition_id)

        assert found == []

    async def test_ignores_enrollments_of_the_same_users_in_another_competition(
        self, db_session, competition_id, creator_id
    ):
        """
        La búsqueda va acotada por competición además de por usuario: la
        misma persona inscrita en dos torneos no arrastra la preferencia del
        otro.
        """
        other_competition = Competition.create(
            id=CompetitionId(uuid4()),
            creator_id=creator_id,
            name=CompetitionName(f"Other Cup {uuid4().hex[:6]}"),
            dates=DateRange(start_date=BASE_DATE, end_date=BASE_DATE + timedelta(days=5)),
            location=Location(main_country=CountryCode("ES")),
            play_mode=PlayMode.SCRATCH,
            team_1_name="Team A",
            team_2_name="Team B",
        )
        await SQLAlchemyCompetitionRepository(db_session).add(other_competition)
        await db_session.commit()

        player = UserId.generate()
        await _insert_user(db_session, player)
        await _enroll(db_session, other_competition.id, player, use_real_name=True)

        repo = SQLAlchemyEnrollmentRepository(db_session)
        found = await repo.find_by_user_ids_and_competition([player], competition_id)

        assert found == []
