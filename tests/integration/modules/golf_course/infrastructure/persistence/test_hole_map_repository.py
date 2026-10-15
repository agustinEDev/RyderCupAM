"""
Integration tests del repositorio de mapas de hoyos (BE #532).

El mapa viaja entero a una fila con los hoyos en JSONB: lo que se comprueba es
que sale de PostgreSQL exactamente como entró (puntos, línea, contorno, orígenes
y revisión), que cada campo tiene un solo mapa y que se va con su campo.
"""

from datetime import UTC, datetime

import pytest
import pytest_asyncio
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError

from src.modules.golf_course.domain.entities.course_hole_map import CourseHoleMap
from src.modules.golf_course.domain.entities.golf_course import GolfCourse
from src.modules.golf_course.domain.entities.hole import Hole
from src.modules.golf_course.domain.entities.tee import Tee
from src.modules.golf_course.domain.value_objects.course_type import CourseType
from src.modules.golf_course.domain.value_objects.geo_point import GeoPoint
from src.modules.golf_course.domain.value_objects.golf_course_id import GolfCourseId
from src.modules.golf_course.domain.value_objects.green_position import GreenPosition
from src.modules.golf_course.domain.value_objects.hole_map_status import HoleMapStatus
from src.modules.golf_course.domain.value_objects.mapped_hole import MappedHole
from src.modules.golf_course.domain.value_objects.position_source import PositionSource
from src.modules.golf_course.domain.value_objects.tee_color import TeeColor
from src.modules.golf_course.infrastructure.persistence.mappers.hole_map_mapper import (
    golf_course_hole_maps_table,
)
from src.modules.golf_course.infrastructure.persistence.repositories.golf_course_repository import (
    GolfCourseRepository,
)
from src.modules.golf_course.infrastructure.persistence.repositories.hole_map_repository import (
    HoleMapRepository,
)
from src.modules.user.domain.value_objects.user_id import UserId
from src.shared.domain.value_objects.country_code import CountryCode
from src.shared.domain.value_objects.gender import Gender

pytestmark = [pytest.mark.integration]

IMPORTADO = datetime(2026, 10, 15, 9, 0)

SALIDA = GeoPoint(latitude=36.285, longitude=-5.329)
CODO = GeoPoint(latitude=36.2865, longitude=-5.3285)
GREEN = GreenPosition(
    front=GeoPoint(latitude=36.2878, longitude=-5.3282),
    center=GeoPoint(latitude=36.2879, longitude=-5.32815),
    back=GeoPoint(latitude=36.288, longitude=-5.3281),
    outline=(
        GeoPoint(latitude=36.28775, longitude=-5.3283),
        GeoPoint(latitude=36.28805, longitude=-5.3283),
        GeoPoint(latitude=36.28805, longitude=-5.328),
    ),
    source=PositionSource.OSM,
)
GREEN_DE_JUGADOR = GreenPosition(
    front=GeoPoint(latitude=36.29, longitude=-5.33),
    center=GeoPoint(latitude=36.2901, longitude=-5.33),
    back=GeoPoint(latitude=36.2902, longitude=-5.33),
    source=PositionSource.PLAYER,
)


async def _insert_user(db_session, user_id: UserId) -> None:
    now = datetime.now(UTC).replace(tzinfo=None)
    await db_session.execute(
        text(
            "INSERT INTO users (id, first_name, last_name, email, password, "
            "created_at, updated_at, email_verified, failed_login_attempts, is_admin) "
            "VALUES (:id, 'Test', 'User', :email, '$2b$04$placeholder', :now, :now, "
            "false, 0, false)"
        ),
        {"id": str(user_id.value), "email": f"test-{user_id.value}@example.com", "now": now},
    )


@pytest_asyncio.fixture
async def creator_id(db_session) -> UserId:
    uid = UserId.generate()
    await _insert_user(db_session, uid)
    return uid


async def _saved_course(db_session, creator_id: UserId) -> GolfCourseId:
    pars = [4, 5, 4, 4, 3, 4, 5, 4, 3, 3, 4, 5, 4, 4, 3, 4, 5, 4]
    holes = [Hole(number=i + 1, par=pars[i], stroke_index=i + 1, meters=350) for i in range(18)]
    tee = Tee(
        color=TeeColor.YELLOW,
        gender=Gender.MALE,
        identifier=None,
        course_rating=71.2,
        slope_rating=128,
    )
    course = GolfCourse.create(
        name="Campo con mapa",
        country_code=CountryCode("ES"),
        course_type=CourseType.STANDARD_18,
        creator_id=creator_id,
        tees=[tee],
        holes=holes,
    )
    await GolfCourseRepository(db_session).save(course)
    await db_session.flush()
    return course.id


def _map(course_id: GolfCourseId) -> CourseHoleMap:
    return CourseHoleMap.create(
        golf_course_id=course_id,
        holes=[
            MappedHole(
                number=1,
                play_line=(SALIDA, CODO, GREEN.center),
                line_source=PositionSource.OSM,
                green=GREEN,
            ),
            MappedHole(
                number=2,
                play_line=(SALIDA, CODO),
                line_source=PositionSource.OSM,
                green=GREEN_DE_JUGADOR,
            ),
            MappedHole(number=3, play_line=(SALIDA, CODO), line_source=PositionSource.MANUAL),
        ],
        osm_reference="way/237391513",
        imported_at=IMPORTADO,
    )


async def _reload(db_session, course_id: GolfCourseId) -> CourseHoleMap | None:
    await db_session.flush()
    db_session.expunge_all()
    return await HoleMapRepository(db_session).find_by_golf_course_id(course_id)


# ============================================================================
# R1 — Ida y vuelta
# ============================================================================


@pytest.mark.asyncio
async def test_r1_pending_map_round_trip(db_session, creator_id):
    """
    GIVEN: Un mapa pendiente con línea con codo, green con contorno, green de
           jugador sin contorno y un hoyo sin green
    WHEN: Se guarda y se vuelve a leer
    THEN: Sale idéntico
    """
    course_id = await _saved_course(db_session, creator_id)
    hole_map = _map(course_id)

    await HoleMapRepository(db_session).save(hole_map)
    found = await _reload(db_session, course_id)

    assert found is not None
    assert found.golf_course_id == course_id
    assert found.status is HoleMapStatus.PENDING_REVIEW
    assert found.holes == hole_map.holes
    assert found.holes[2].green is None
    assert found.osm_reference == "way/237391513"
    assert found.imported_at == IMPORTADO
    assert found.reviewed_by is None
    assert found.reviewed_at is None
    assert found.rejection_reason is None


@pytest.mark.asyncio
async def test_r1_review_round_trip(db_session, creator_id):
    """
    GIVEN: Un mapa rechazado con motivo
    WHEN: Se guarda y se vuelve a leer
    THEN: Conserva estado, revisor, fecha y motivo
    """
    course_id = await _saved_course(db_session, creator_id)
    hole_map = _map(course_id)
    hole_map.reject(reviewer_id=creator_id, reason="Hoyos de otro recorrido")

    await HoleMapRepository(db_session).save(hole_map)
    found = await _reload(db_session, course_id)

    assert found is not None
    assert found.status is HoleMapStatus.REJECTED
    assert found.reviewed_by == creator_id
    assert found.reviewed_at == hole_map.reviewed_at
    assert found.rejection_reason == "Hoyos de otro recorrido"


# ============================================================================
# R2 — Un mapa por campo
# ============================================================================


@pytest.mark.asyncio
async def test_r2_saving_again_updates_the_same_row(db_session, creator_id):
    """
    GIVEN: Un mapa guardado
    WHEN: Se lee, se aprueba y se guarda de nuevo
    THEN: Hay una sola fila y refleja la aprobación
    """
    course_id = await _saved_course(db_session, creator_id)
    repository = HoleMapRepository(db_session)
    await repository.save(_map(course_id))
    loaded = await _reload(db_session, course_id)
    assert loaded is not None

    loaded.approve(reviewer_id=creator_id)
    await repository.save(loaded)
    found = await _reload(db_session, course_id)

    count = await db_session.scalar(select(func.count()).select_from(golf_course_hole_maps_table))
    assert count == 1
    assert found is not None
    assert found.status is HoleMapStatus.APPROVED


@pytest.mark.asyncio
async def test_r2_reimported_holes_are_written(db_session, creator_id):
    """
    GIVEN: Un mapa pendiente guardado
    WHEN: Se lee, se reimporta con otros hoyos y se guarda
    THEN: La base de datos tiene los hoyos nuevos (el JSONB se reescribe)
    """
    course_id = await _saved_course(db_session, creator_id)
    repository = HoleMapRepository(db_session)
    await repository.save(_map(course_id))
    loaded = await _reload(db_session, course_id)
    assert loaded is not None

    nuevo = MappedHole(number=9, play_line=(CODO, SALIDA), line_source=PositionSource.OSM)
    loaded.reimport(holes=[nuevo], osm_reference="relation/7", imported_at=IMPORTADO)
    await repository.save(loaded)
    found = await _reload(db_session, course_id)

    assert found is not None
    assert found.holes == (nuevo,)
    assert found.osm_reference == "relation/7"


# ============================================================================
# R3-R5 — Cascada, pendientes y campo sin mapa
# ============================================================================


@pytest.mark.asyncio
async def test_r3_deleting_course_deletes_its_map(db_session, creator_id):
    """
    GIVEN: Un campo con mapa
    WHEN: Se borra el campo
    THEN: Su mapa desaparece con él
    """
    course_id = await _saved_course(db_session, creator_id)
    await HoleMapRepository(db_session).save(_map(course_id))
    await db_session.flush()

    await db_session.execute(
        text("DELETE FROM golf_courses WHERE id = :id"), {"id": course_id.value}
    )

    assert await _reload(db_session, course_id) is None


@pytest.mark.asyncio
async def test_r4_find_pending_returns_only_pending(db_session, creator_id):
    """
    GIVEN: Tres campos con mapas pendiente, aprobado y rechazado
    WHEN: Se piden los pendientes
    THEN: Sale solo el pendiente
    """
    repository = HoleMapRepository(db_session)
    pendiente = _map(await _saved_course(db_session, creator_id))
    aprobado = _map(await _saved_course(db_session, creator_id))
    aprobado.approve(reviewer_id=creator_id)
    rechazado = _map(await _saved_course(db_session, creator_id))
    rechazado.reject(reviewer_id=creator_id)
    for hole_map in (pendiente, aprobado, rechazado):
        await repository.save(hole_map)
    await db_session.flush()
    db_session.expunge_all()

    pending = await repository.find_pending()

    assert [m.golf_course_id for m in pending] == [pendiente.golf_course_id]


@pytest.mark.asyncio
async def test_r5_course_without_map_returns_none(db_session, creator_id):
    """
    GIVEN: Un campo sin mapa
    WHEN: Se busca su mapa
    THEN: Devuelve None
    """
    course_id = await _saved_course(db_session, creator_id)

    assert await _reload(db_session, course_id) is None


# ============================================================================
# R6-R8 — Revisor borrado, reimportar un rechazado y restricciones de la BD
# ============================================================================


@pytest.mark.asyncio
async def test_r6_deleting_the_reviewer_keeps_the_review(db_session, creator_id):
    """
    GIVEN: Un mapa aprobado por un admin
    WHEN: Se borra a ese admin
    THEN: El mapa sigue aprobado, con su fecha de revisión y sin revisor
    """
    course_id = await _saved_course(db_session, creator_id)
    admin = UserId.generate()
    await _insert_user(db_session, admin)
    hole_map = _map(course_id)
    hole_map.approve(reviewer_id=admin)
    await HoleMapRepository(db_session).save(hole_map)
    await db_session.flush()

    await db_session.execute(text("DELETE FROM users WHERE id = :id"), {"id": str(admin.value)})
    found = await _reload(db_session, course_id)

    assert found is not None
    assert found.status is HoleMapStatus.APPROVED
    assert found.reviewed_by is None
    assert found.reviewed_at == hole_map.reviewed_at


@pytest.mark.asyncio
async def test_r7_reimporting_a_rejected_map_clears_the_review(db_session, creator_id):
    """
    GIVEN: Un mapa rechazado y guardado
    WHEN: Se lee, se reimporta y se guarda
    THEN: Vuelve a pendiente en la BD, sin revisor, fecha ni motivo
    """
    course_id = await _saved_course(db_session, creator_id)
    repository = HoleMapRepository(db_session)
    hole_map = _map(course_id)
    hole_map.reject(reviewer_id=creator_id, reason="Otro recorrido")
    await repository.save(hole_map)
    loaded = await _reload(db_session, course_id)
    assert loaded is not None

    loaded.reimport(holes=hole_map.holes[:1], osm_reference="way/8", imported_at=IMPORTADO)
    await repository.save(loaded)
    found = await _reload(db_session, course_id)

    assert found is not None
    assert found.status is HoleMapStatus.PENDING_REVIEW
    assert found.reviewed_by is None
    assert found.reviewed_at is None
    assert found.rejection_reason is None
    assert len(found.holes) == 1


async def _insert_raw(db_session, course_id, status, reviewed_at, reason=None):
    await db_session.execute(
        text(
            "INSERT INTO golf_course_hole_maps (golf_course_id, holes, osm_reference, "
            "imported_at, status, reviewed_at, rejection_reason, created_at, updated_at) "
            "VALUES (:id, '[]', 'way/1', :now, :status, :reviewed_at, :reason, :now, :now)"
        ),
        {
            "id": course_id.value,
            "now": IMPORTADO,
            "status": status,
            "reviewed_at": reviewed_at,
            "reason": reason,
        },
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("status", "reviewed", "reason"),
    [
        ("DRAFT", True, None),  # estado que no existe (con fecha: solo lo para su CHECK)
        ("APPROVED", False, None),  # revisado sin fecha de revisión
        ("PENDING_REVIEW", True, None),  # pendiente con fecha de revisión
        ("APPROVED", True, "motivo"),  # motivo de rechazo en un mapa aprobado
    ],
)
async def test_r8_database_rejects_inconsistent_rows(
    db_session, creator_id, status, reviewed, reason
):
    """
    GIVEN: Una fila escrita a mano que rompe una regla del mapa
    WHEN: Se inserta
    THEN: La propia base de datos la rechaza
    """
    course_id = await _saved_course(db_session, creator_id)

    with pytest.raises(IntegrityError):
        await _insert_raw(db_session, course_id, status, IMPORTADO if reviewed else None, reason)
