"""
Integration tests de la procedencia contra PostgreSQL.

Comprueban que el origen sobrevive al viaje de ida y vuelta y que las
restricciones están en la base de datos: la importación escribe cientos de
filas de una vez, y un campo marcado como federado sin fecha de importación o
con un identificador repetido pasaría inadvertido.
"""

from datetime import UTC, datetime

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from src.modules.golf_course.domain.entities.golf_course import GolfCourse
from src.modules.golf_course.domain.entities.hole import Hole
from src.modules.golf_course.domain.entities.tee import Tee
from src.modules.golf_course.domain.value_objects.course_provenance import CourseProvenance
from src.modules.golf_course.domain.value_objects.course_source import CourseSource
from src.modules.golf_course.domain.value_objects.course_type import CourseType
from src.modules.golf_course.domain.value_objects.tee_color import TeeColor
from src.modules.golf_course.infrastructure.persistence.repositories.golf_course_repository import (
    GolfCourseRepository,
)
from src.modules.user.domain.value_objects.user_id import UserId
from src.shared.domain.value_objects.country_code import CountryCode
from src.shared.domain.value_objects.gender import Gender

pytestmark = [pytest.mark.integration]

IMPORTED_AT = datetime(2026, 8, 12, 10, 0, 0)
RFEG_PROVENANCE = CourseProvenance(
    source=CourseSource.RFEG, external_id="3727", imported_at=IMPORTED_AT
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


def _build_course(
    creator_id, tees, holes, name="Campo federado", provenance=None, physical_holes=None
) -> GolfCourse:
    """Crea un campo con la procedencia dada."""
    return GolfCourse.create(
        name=name,
        country_code=CountryCode("ES"),
        course_type=CourseType.STANDARD_18,
        creator_id=creator_id,
        tees=tees,
        holes=holes,
        provenance=provenance,
        physical_holes=physical_holes,
    )


# ============================================================================
# Tests: ida y vuelta
# ============================================================================


@pytest.mark.asyncio
async def test_imported_course_keeps_provenance(db_session, creator_id, valid_tees, valid_holes):
    """
    GIVEN: Un campo importado de la RFEG, de nueve hoyos físicos
    WHEN: Se persiste y se vuelve a leer
    THEN: Conserva origen, identificador externo, fecha y hoyos físicos
    """
    repository = GolfCourseRepository(db_session)
    course = _build_course(
        creator_id, valid_tees, valid_holes, provenance=RFEG_PROVENANCE, physical_holes=9
    )

    await repository.save(course)
    await db_session.flush()
    db_session.expunge_all()

    found = await repository.find_by_id(course.id)

    assert found is not None
    assert found.provenance == RFEG_PROVENANCE
    assert found.physical_holes == 9


@pytest.mark.asyncio
async def test_manual_course_defaults_to_manual_source(
    db_session, creator_id, valid_tees, valid_holes
):
    """
    GIVEN: Un campo dado de alta sin procedencia
    WHEN: Se persiste y se vuelve a leer
    THEN: Consta como manual, sin identificador ni fecha
    """
    repository = GolfCourseRepository(db_session)
    course = _build_course(creator_id, valid_tees, valid_holes)

    await repository.save(course)
    await db_session.flush()
    db_session.expunge_all()

    found = await repository.find_by_id(course.id)

    assert found is not None
    assert found.provenance.source is CourseSource.MANUAL
    assert found.provenance.is_imported is False
    assert found.physical_holes is None


# ============================================================================
# Tests: restricciones en la base de datos
# ============================================================================


@pytest.mark.asyncio
async def test_the_same_course_cannot_be_imported_twice(
    db_session, creator_id, valid_tees, valid_holes
):
    """
    GIVEN: Un campo ya importado de la RFEG
    WHEN: Se intenta guardar otro con el mismo origen e identificador
    THEN: La base de datos lo rechaza

    Es lo que hace que reimportar actualice en vez de duplicar, aunque el
    importador tuviera un fallo.
    """
    repository = GolfCourseRepository(db_session)
    first = _build_course(
        creator_id, valid_tees, valid_holes, name="Primero", provenance=RFEG_PROVENANCE
    )
    await repository.save(first)
    await db_session.flush()

    duplicate = _build_course(
        creator_id,
        [
            Tee(
                color=TeeColor.YELLOW,
                gender=Gender.MALE,
                identifier=None,
                course_rating=71.2,
                slope_rating=128,
            )
        ],
        valid_holes,
        name="Duplicado",
        provenance=RFEG_PROVENANCE,
    )

    with pytest.raises(IntegrityError):
        await repository.save(duplicate)
        await db_session.flush()


@pytest.mark.asyncio
async def test_manual_courses_do_not_collide_with_each_other(
    db_session, creator_id, valid_tees, valid_holes
):
    """
    GIVEN: Dos campos manuales, ambos sin identificador externo
    WHEN: Se guardan
    THEN: Conviven

    El índice de unicidad es parcial justamente por esto: si no lo fuera, todos
    los campos manuales chocarían entre sí.
    """
    repository = GolfCourseRepository(db_session)
    first = _build_course(creator_id, valid_tees, valid_holes, name="Manual uno")
    second = _build_course(
        creator_id,
        [
            Tee(
                color=TeeColor.WHITE,
                gender=Gender.MALE,
                identifier=None,
                course_rating=73.0,
                slope_rating=133,
            )
        ],
        valid_holes,
        name="Manual dos",
    )

    await repository.save(first)
    await repository.save(second)
    await db_session.flush()

    assert await repository.find_by_id(first.id) is not None
    assert await repository.find_by_id(second.id) is not None


@pytest.mark.asyncio
async def test_database_rejects_an_imported_course_without_date(
    db_session, creator_id, valid_tees, valid_holes
):
    """
    GIVEN: Un campo guardado
    WHEN: Se intenta marcarlo como federado sin fecha de importación por SQL
    THEN: La base de datos lo rechaza, aunque el dominio no intervenga
    """
    repository = GolfCourseRepository(db_session)
    course = _build_course(creator_id, valid_tees, valid_holes)
    await repository.save(course)
    await db_session.flush()

    with pytest.raises(IntegrityError):
        await db_session.execute(
            text("UPDATE golf_courses SET source = 'RFEG' WHERE id = :id"),
            {"id": str(course.id.value)},
        )
        await db_session.flush()


@pytest.mark.asyncio
async def test_database_rejects_impossible_physical_holes(
    db_session, creator_id, valid_tees, valid_holes
):
    """
    GIVEN: Un campo guardado
    WHEN: Se intenta escribir un número de hoyos físicos que no es 9 ni 18
    THEN: La base de datos lo rechaza
    """
    repository = GolfCourseRepository(db_session)
    course = _build_course(creator_id, valid_tees, valid_holes)
    await repository.save(course)
    await db_session.flush()

    with pytest.raises(IntegrityError):
        await db_session.execute(
            text("UPDATE golf_courses SET physical_holes = 27 WHERE id = :id"),
            {"id": str(course.id.value)},
        )
        await db_session.flush()
