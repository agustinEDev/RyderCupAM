"""
Integration tests for golf course location persistence.

Comprueban que la ubicación sobrevive al viaje completo hasta PostgreSQL y de
vuelta, y que las restricciones que protegen las coordenadas están en la base de
datos y no solo en el dominio: la importación masiva escribe muchas filas de
golpe y un dato a medias pasaría inadvertido.
"""

from datetime import UTC, datetime

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

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

DERIO = CourseLocation(
    latitude=43.29519,
    longitude=-2.87352,
    address="CALLE EREAGA BIDEA S/N, 48160, DERIO, VIZCAYA",
    city="DERIO",
    province="VIZCAYA",
)


async def _insert_test_user(db_session, user_id: UserId) -> None:
    """Insert a minimal user row so golf_courses.creator_id FK is satisfied."""
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
            "ln": "User",
            "email": f"test-{user_id.value}@example.com",
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
    """Provide a UserId backed by an actual user row in the test DB."""
    uid = UserId.generate()
    await _insert_test_user(db_session, uid)
    return uid


@pytest.fixture
def valid_tees():
    """Una salida amarilla masculina."""
    return [
        Tee(
            color=TeeColor.YELLOW,
            gender=Gender.MALE,
            identifier=None,
            course_rating=71.2,
            slope_rating=128,
        )
    ]


@pytest.fixture
def valid_holes():
    """Tarjeta de 18 hoyos, par 72."""
    pars = [4, 5, 4, 4, 3, 4, 5, 4, 3, 3, 4, 5, 4, 4, 3, 4, 5, 4]
    return [Hole(number=i + 1, par=pars[i], stroke_index=i + 1, meters=350) for i in range(18)]


def _build_course(creator_id, tees, holes, location=None) -> GolfCourse:
    """Crea un campo con la ubicación dada."""
    return GolfCourse.create(
        name="Campo de prueba de ubicación",
        country_code=CountryCode("ES"),
        course_type=CourseType.STANDARD_18,
        creator_id=creator_id,
        tees=tees,
        holes=holes,
        location=location,
    )


# ============================================================================
# Tests: ida y vuelta a la base de datos
# ============================================================================


@pytest.mark.asyncio
async def test_save_and_find_course_with_location(db_session, creator_id, valid_tees, valid_holes):
    """
    GIVEN: Un campo con ubicación completa
    WHEN: Se persiste y se vuelve a leer
    THEN: Conserva coordenadas, dirección, localidad y provincia
    """
    repository = GolfCourseRepository(db_session)
    course = _build_course(creator_id, valid_tees, valid_holes, location=DERIO)

    await repository.save(course)
    await db_session.flush()
    db_session.expunge_all()

    found = await repository.find_by_id(course.id)

    assert found is not None
    assert found.location == DERIO
    assert found.location.has_coordinates is True


@pytest.mark.asyncio
async def test_save_and_find_course_without_location(
    db_session, creator_id, valid_tees, valid_holes
):
    """
    GIVEN: Un campo sin ubicación
    WHEN: Se persiste y se vuelve a leer
    THEN: Devuelve una ubicación vacía, no un error
    """
    repository = GolfCourseRepository(db_session)
    course = _build_course(creator_id, valid_tees, valid_holes)

    await repository.save(course)
    await db_session.flush()
    db_session.expunge_all()

    found = await repository.find_by_id(course.id)

    assert found is not None
    assert found.location.is_empty is True


@pytest.mark.asyncio
async def test_updating_location_persists(db_session, creator_id, valid_tees, valid_holes):
    """
    GIVEN: Un campo ya guardado con ubicación
    WHEN: Se le cambia la ubicación y se vuelve a guardar
    THEN: La base de datos refleja la nueva
    """
    repository = GolfCourseRepository(db_session)
    course = _build_course(creator_id, valid_tees, valid_holes, location=DERIO)
    await repository.save(course)
    await db_session.flush()

    marbella = CourseLocation(latitude=36.50, longitude=-4.88, city="MARBELLA", province="MÁLAGA")
    course.update(
        name=course.name,
        country_code=course.country_code,
        course_type=course.course_type,
        tees=valid_tees,
        holes=valid_holes,
        location=marbella,
    )
    await repository.save(course)
    await db_session.flush()
    db_session.expunge_all()

    found = await repository.find_by_id(course.id)

    assert found is not None
    assert found.location.city == "MARBELLA"
    assert found.location.latitude == 36.50


# ============================================================================
# Tests: restricciones en la base de datos
# ============================================================================


@pytest.mark.asyncio
async def test_database_rejects_half_coordinates(db_session, creator_id, valid_tees, valid_holes):
    """
    GIVEN: Un campo ya guardado
    WHEN: Se intenta dejar solo la latitud por SQL directo
    THEN: La base de datos lo rechaza, aunque el dominio no intervenga
    """
    repository = GolfCourseRepository(db_session)
    course = _build_course(creator_id, valid_tees, valid_holes, location=DERIO)
    await repository.save(course)
    await db_session.flush()

    with pytest.raises(IntegrityError):
        await db_session.execute(
            text("UPDATE golf_courses SET longitude = NULL WHERE id = :id"),
            {"id": str(course.id.value)},
        )
        await db_session.flush()


@pytest.mark.asyncio
async def test_database_rejects_impossible_latitude(
    db_session, creator_id, valid_tees, valid_holes
):
    """
    GIVEN: Un campo ya guardado
    WHEN: Se intenta escribir una latitud fuera de rango por SQL directo
    THEN: La base de datos lo rechaza
    """
    repository = GolfCourseRepository(db_session)
    course = _build_course(creator_id, valid_tees, valid_holes, location=DERIO)
    await repository.save(course)
    await db_session.flush()

    with pytest.raises(IntegrityError):
        await db_session.execute(
            text("UPDATE golf_courses SET latitude = 120.0 WHERE id = :id"),
            {"id": str(course.id.value)},
        )
        await db_session.flush()
