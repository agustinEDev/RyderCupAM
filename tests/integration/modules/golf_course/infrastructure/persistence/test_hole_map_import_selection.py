"""
Integration tests: qué campos recorre el comando de importar mapas de OSM (BE #532).

Solo campos aprobados y con coordenadas, del país pedido o el campo pedido.
"""

from datetime import UTC, datetime

import pytest
import pytest_asyncio
from sqlalchemy import text

from scripts.import_hole_maps import select_course_ids
from src.modules.golf_course.domain.entities.golf_course import GolfCourse
from src.modules.golf_course.domain.entities.hole import Hole
from src.modules.golf_course.domain.entities.tee import Tee
from src.modules.golf_course.domain.value_objects.course_location import CourseLocation
from src.modules.golf_course.domain.value_objects.course_type import CourseType
from src.modules.golf_course.domain.value_objects.tee_color import TeeColor
from src.modules.golf_course.infrastructure.persistence.repositories.golf_course_repository import (
    GolfCourseRepository,
)
from src.modules.user.domain.value_objects.user_id import UserId
from src.shared.domain.value_objects.country_code import CountryCode
from src.shared.domain.value_objects.gender import Gender

pytestmark = [pytest.mark.integration]

PARES = [4, 5, 4, 4, 3, 4, 5, 4, 3, 3, 4, 5, 4, 4, 3, 4, 5, 4]
SITIO = CourseLocation(latitude=36.2858, longitude=-5.3247)


@pytest_asyncio.fixture
async def creator_id(db_session) -> UserId:
    uid = UserId.generate()
    now = datetime.now(UTC).replace(tzinfo=None)
    await db_session.execute(
        text(
            "INSERT INTO users (id, first_name, last_name, email, password, "
            "created_at, updated_at, email_verified, failed_login_attempts, is_admin) "
            "VALUES (:id, 'Test', 'User', :email, '$2b$04$placeholder', :now, :now, "
            "false, 0, false)"
        ),
        {"id": str(uid.value), "email": f"test-{uid.value}@example.com", "now": now},
    )
    return uid


async def _course(db_session, creator_id, *, country="ES", location=SITIO, approved=True):
    course = GolfCourse.create(
        name=f"Campo {country} {approved}",
        country_code=CountryCode(country),
        course_type=CourseType.STANDARD_18,
        creator_id=creator_id,
        tees=[
            Tee(
                color=TeeColor.YELLOW,
                gender=Gender.MALE,
                identifier=None,
                course_rating=71.2,
                slope_rating=128,
            )
        ],
        holes=[Hole(number=i + 1, par=PARES[i], stroke_index=i + 1, meters=350) for i in range(18)],
        location=location,
    )
    if approved:
        course.approve()
    await GolfCourseRepository(db_session).save(course)
    await db_session.flush()
    return str(course.id)


@pytest.mark.asyncio
async def test_s1_country_selects_approved_courses_with_coordinates(db_session, creator_id):
    """
    GIVEN: En España un campo aprobado con coordenadas, uno sin coordenadas y
           uno pendiente; en Portugal uno aprobado con coordenadas
    WHEN: Se eligen los campos de ES
    THEN: Sale solo el aprobado con coordenadas de España
    """
    bueno = await _course(db_session, creator_id)
    await _course(db_session, creator_id, location=None)
    await _course(db_session, creator_id, approved=False)
    await _course(db_session, creator_id, country="PT")

    assert await select_course_ids(db_session, country="ES") == [bueno]


@pytest.mark.asyncio
async def test_s1_course_selects_that_one_if_it_qualifies(db_session, creator_id):
    """
    GIVEN: Un campo aprobado con coordenadas y otro pendiente
    WHEN: Se elige cada uno por su id
    THEN: El aprobado sale; el pendiente no
    """
    bueno = await _course(db_session, creator_id)
    pendiente = await _course(db_session, creator_id, approved=False)

    assert await select_course_ids(db_session, course=bueno) == [bueno]
    assert await select_course_ids(db_session, course=pendiente) == []
