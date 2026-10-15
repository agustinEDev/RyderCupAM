"""
Integration tests: un admin aprueba el mapa mientras se espera a OSM (BE #532).

Contra PostgreSQL y con dos sesiones, porque en memoria no se ve el fallo: la
sesión del importador ya tiene el mapa cargado, y una lectura normal le
devolvería esa copia vieja (pendiente) en vez de la aprobada en la base de datos.
"""

import asyncio
from datetime import UTC, datetime

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.golf_course.application.dtos.hole_map_import_dtos import (
    ImportHoleMapRequestDTO,
    ImportHoleMapStatus,
)
from src.modules.golf_course.application.ports.osm_hole_map_source import (
    IOsmHoleMapSource,
    OsmHoleMapCandidate,
)
from src.modules.golf_course.application.use_cases.import_hole_map_from_osm_use_case import (
    ImportHoleMapFromOsmUseCase,
)
from src.modules.golf_course.domain.entities.course_hole_map import CourseHoleMap
from src.modules.golf_course.domain.entities.golf_course import GolfCourse
from src.modules.golf_course.domain.entities.hole import Hole
from src.modules.golf_course.domain.entities.tee import Tee
from src.modules.golf_course.domain.value_objects.course_location import CourseLocation
from src.modules.golf_course.domain.value_objects.course_type import CourseType
from src.modules.golf_course.domain.value_objects.geo_point import GeoPoint
from src.modules.golf_course.domain.value_objects.hole_map_status import HoleMapStatus
from src.modules.golf_course.domain.value_objects.mapped_hole import MappedHole
from src.modules.golf_course.domain.value_objects.position_source import PositionSource
from src.modules.golf_course.domain.value_objects.tee_color import TeeColor
from src.modules.golf_course.infrastructure.persistence.repositories.golf_course_repository import (
    GolfCourseRepository,
)
from src.modules.golf_course.infrastructure.persistence.repositories.hole_map_repository import (
    HoleMapRepository,
)
from src.modules.golf_course.infrastructure.persistence.sqlalchemy.golf_course_unit_of_work import (
    SQLAlchemyGolfCourseUnitOfWork,
)
from src.modules.user.domain.value_objects.user_id import UserId
from src.shared.domain.value_objects.country_code import CountryCode
from src.shared.domain.value_objects.gender import Gender

pytestmark = [pytest.mark.integration]

PARES = [4, 5, 4, 4, 3, 4, 5, 4, 3, 3, 4, 5, 4, 4, 3, 4, 5, 4]


def _hole(number: int) -> MappedHole:
    return MappedHole(
        number=number,
        play_line=(
            GeoPoint(latitude=36.28, longitude=-5.33),
            GeoPoint(latitude=36.29, longitude=-5.33),
        ),
        line_source=PositionSource.OSM,
    )


@pytest_asyncio.fixture
async def escenario(db_session):
    """Un campo aprobado con un mapa pendiente (hoyo 9), confirmado en la BD."""
    admin = UserId.generate()
    now = datetime.now(UTC).replace(tzinfo=None)
    await db_session.execute(
        text(
            "INSERT INTO users (id, first_name, last_name, email, password, "
            "created_at, updated_at, email_verified, failed_login_attempts, is_admin) "
            "VALUES (:id, 'Admin', 'User', :email, '$2b$04$placeholder', :now, :now, "
            "false, 0, true)"
        ),
        {"id": str(admin.value), "email": f"admin-{admin.value}@example.com", "now": now},
    )
    course = GolfCourse.create(
        name="Club de Golf Valderrama",
        country_code=CountryCode("ES"),
        course_type=CourseType.STANDARD_18,
        creator_id=admin,
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
        location=CourseLocation(latitude=36.2858, longitude=-5.3247),
    )
    course.approve()
    await GolfCourseRepository(db_session).save(course)
    pending = CourseHoleMap.create(
        golf_course_id=course.id,
        holes=[_hole(9)],
        osm_reference="way/1",
        imported_at=datetime(2026, 10, 1, 9, 0),
    )
    await HoleMapRepository(db_session).save(pending)
    await db_session.commit()
    return course, admin


async def _approve_elsewhere(db_session, course_id, admin) -> None:
    """Otra sesión (el admin, en la app) aprueba el mapa y confirma."""
    async with AsyncSession(bind=db_session.bind, expire_on_commit=False) as other:
        repository = HoleMapRepository(other)
        hole_map = await repository.find_by_golf_course_id(course_id)
        assert hole_map is not None
        hole_map.approve(reviewer_id=admin)
        await repository.save(hole_map)
        await other.commit()


@pytest.mark.asyncio
async def test_for_update_read_sees_an_approval_made_in_another_session(db_session, escenario):
    """
    GIVEN: El mapa pendiente ya cargado en la sesión del importador
    WHEN: Otra sesión lo aprueba y se vuelve a leer para actualizar
    THEN: Se ve aprobado (no la copia vieja de la sesión)
    """
    course, admin = escenario
    repository = HoleMapRepository(db_session)
    loaded = await repository.find_by_golf_course_id(course.id)
    assert loaded is not None and loaded.status is HoleMapStatus.PENDING_REVIEW
    await db_session.commit()

    await _approve_elsewhere(db_session, course.id, admin)
    fresh = await repository.find_by_golf_course_id_for_update(course.id)

    assert fresh is not None
    assert fresh.status is HoleMapStatus.APPROVED


@pytest.mark.asyncio
async def test_map_approved_while_asking_osm_is_not_overwritten(db_session, escenario):
    """
    GIVEN: Un mapa pendiente y un admin que lo aprueba mientras se espera a OSM
    WHEN: Termina la importación con --apply
    THEN: «Ya aprobado», y en la BD sigue aprobado con su hoyo 9
    """
    course, admin = escenario
    retenido = []

    class FuenteLenta(IOsmHoleMapSource):
        async def find(self, **_kwargs):
            # La sesión del importador conserva su copia del mapa (pendiente): una
            # relectura normal la devolvería en vez de la aprobada
            retenido.append(await HoleMapRepository(db_session).find_by_golf_course_id(course.id))
            await db_session.commit()
            await _approve_elsewhere(db_session, course.id, admin)
            return OsmHoleMapCandidate(osm_reference="way/2", holes=(_hole(1), _hole(2)))

    use_case = ImportHoleMapFromOsmUseCase(
        SQLAlchemyGolfCourseUnitOfWork(db_session), FuenteLenta()
    )

    result = await use_case.execute(
        ImportHoleMapRequestDTO(golf_course_id=str(course.id), apply=True)
    )

    assert result.status is ImportHoleMapStatus.SKIPPED_APPROVED
    row = (
        await db_session.execute(
            text("SELECT status, holes FROM golf_course_hole_maps WHERE golf_course_id = :id"),
            {"id": course.id.value},
        )
    ).one()
    assert row.status == "APPROVED"
    assert [hole["number"] for hole in row.holes] == [9]


@pytest.mark.asyncio
async def test_two_imports_of_the_same_course_queue_up(db_session, escenario):
    """
    GIVEN: Un campo SIN mapa y dos importaciones que van a escribir a la vez
    WHEN: La primera relee para escribir (bloqueo) y la segunda también
    THEN: La segunda espera a que la primera confirme y entonces ve su mapa
         (lo reimportará), en vez de crear un segundo y chocar
    """
    course, _ = escenario
    await db_session.execute(
        text("DELETE FROM golf_course_hole_maps WHERE golf_course_id = :id"),
        {"id": course.id.value},
    )
    await db_session.commit()

    async with AsyncSession(bind=db_session.bind, expire_on_commit=False) as primera:
        repo_a = HoleMapRepository(primera)
        assert await repo_a.find_by_golf_course_id_for_update(course.id) is None

        async def segunda():
            async with AsyncSession(bind=db_session.bind, expire_on_commit=False) as otra:
                return await HoleMapRepository(otra).find_by_golf_course_id_for_update(course.id)

        espera = asyncio.create_task(segunda())
        await asyncio.sleep(0.5)
        assert not espera.done(), "la segunda tenía que quedarse esperando"

        await repo_a.save(
            CourseHoleMap.create(
                golf_course_id=course.id,
                holes=[_hole(1)],
                osm_reference="way/3",
                imported_at=datetime(2026, 10, 15, 9, 0),
            )
        )
        await primera.commit()

    seen = await asyncio.wait_for(espera, timeout=10)
    assert seen is not None
    assert seen.osm_reference == "way/3"
