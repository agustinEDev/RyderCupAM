"""
Tests de los casos de uso del mapa de hoyos: verlo y revisarlo (BE #532).

El jugador solo ve un mapa aprobado. El admin aprueba o rechaza la versión que
tiene delante: si mientras la miraba se reimportó, no vale.
"""

from datetime import UTC, datetime, timedelta, timezone

import pytest

from src.modules.golf_course.application.dtos.hole_map_dtos import ReviewHoleMapRequestDTO
from src.modules.golf_course.application.exceptions import (
    HoleMapChangedError,
    HoleMapNotFoundError,
    HoleMapNotPendingError,
)
from src.modules.golf_course.application.use_cases.hole_map_use_cases import (
    ApproveHoleMapUseCase,
    GetApprovedHoleMapUseCase,
    GetHoleMapForReviewUseCase,
    ListPendingHoleMapsUseCase,
    RejectHoleMapUseCase,
)
from src.modules.golf_course.domain.entities.course_hole_map import CourseHoleMap
from src.modules.golf_course.domain.entities.golf_course import GolfCourse
from src.modules.golf_course.domain.entities.hole import Hole
from src.modules.golf_course.domain.entities.tee import Tee
from src.modules.golf_course.domain.value_objects.course_type import CourseType
from src.modules.golf_course.domain.value_objects.geo_point import GeoPoint
from src.modules.golf_course.domain.value_objects.golf_course_id import GolfCourseId
from src.modules.golf_course.domain.value_objects.hole_map_status import HoleMapStatus
from src.modules.golf_course.domain.value_objects.mapped_hole import MappedHole
from src.modules.golf_course.domain.value_objects.position_source import PositionSource
from src.modules.golf_course.domain.value_objects.tee_color import TeeColor
from src.modules.golf_course.infrastructure.persistence.in_memory.in_memory_golf_course_unit_of_work import (
    InMemoryGolfCourseUnitOfWork,
)
from src.modules.user.domain.value_objects.user_id import UserId
from src.shared.domain.value_objects.country_code import CountryCode
from src.shared.domain.value_objects.gender import Gender

PARES = [4, 5, 4, 4, 3, 4, 5, 4, 3, 3, 4, 5, 4, 4, 3, 4, 5, 4]
IMPORTADO = datetime(2026, 10, 15, 9, 0, 0, 123456)
ADMIN = UserId.generate()


def _course(name="Valderrama") -> GolfCourse:
    course = GolfCourse.create(
        name=name,
        country_code=CountryCode("ES"),
        course_type=CourseType.STANDARD_18,
        creator_id=UserId.generate(),
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
    )
    course.approve()
    return course


def _hole(number: int) -> MappedHole:
    return MappedHole(
        number=number,
        play_line=(
            GeoPoint(latitude=36.28, longitude=-5.33),
            GeoPoint(latitude=36.29, longitude=-5.33),
        ),
        line_source=PositionSource.OSM,
    )


def _map(course_id: GolfCourseId, imported_at=IMPORTADO, holes=(1, 2)) -> CourseHoleMap:
    return CourseHoleMap.create(
        golf_course_id=course_id,
        holes=[_hole(n) for n in holes],
        osm_reference="way/1",
        imported_at=imported_at,
    )


async def _setup(status=HoleMapStatus.PENDING_REVIEW):
    uow = InMemoryGolfCourseUnitOfWork()
    course = _course()
    await uow.golf_courses.save(course)
    hole_map = _map(course.id)
    if status is HoleMapStatus.APPROVED:
        hole_map.approve(reviewer_id=UserId.generate())
    elif status is HoleMapStatus.REJECTED:
        hole_map.reject(reviewer_id=UserId.generate())
    await uow.hole_maps.save(hole_map)
    return uow, course, hole_map


# ============================================================================
# P — Mapa para el jugador
# ============================================================================


@pytest.mark.asyncio
async def test_p1_approved_map_is_returned():
    """
    GIVEN: Un mapa aprobado
    WHEN: Se pide el mapa del campo
    THEN: Sale, en GeoJSON
    """
    uow, course, _ = await _setup(HoleMapStatus.APPROVED)

    dto = await GetApprovedHoleMapUseCase(uow).execute(str(course.id))

    assert dto.status == "APPROVED"
    assert len(dto.geojson.features) == 2


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [HoleMapStatus.PENDING_REVIEW, HoleMapStatus.REJECTED])
async def test_p2_pending_or_rejected_map_is_not_found(status):
    """
    GIVEN: Un mapa pendiente o rechazado
    WHEN: Se pide el mapa del campo
    THEN: No se encuentra: el jugador solo ve lo revisado
    """
    uow, course, _ = await _setup(status)

    with pytest.raises(HoleMapNotFoundError):
        await GetApprovedHoleMapUseCase(uow).execute(str(course.id))


@pytest.mark.asyncio
async def test_p3_course_without_map_is_not_found():
    """
    GIVEN: Un campo sin mapa (o que no existe)
    WHEN: Se pide su mapa
    THEN: No se encuentra
    """
    uow = InMemoryGolfCourseUnitOfWork()

    with pytest.raises(HoleMapNotFoundError):
        await GetApprovedHoleMapUseCase(uow).execute(str(GolfCourseId.generate()))


# ============================================================================
# A1-A2 — Lo que ve el admin
# ============================================================================


@pytest.mark.asyncio
async def test_a1_pending_list_oldest_first_with_course_name_and_counts():
    """
    GIVEN: Dos mapas pendientes (uno con un hoyo sin green) y uno aprobado
    WHEN: El admin pide los pendientes
    THEN: Salen los dos pendientes, el más antiguo primero, con nombre del
         campo, hoyos, hoyos sin green, fecha y referencia OSM
    """
    uow = InMemoryGolfCourseUnitOfWork()
    nuevo, viejo, aprobado = _course("Nuevo"), _course("Viejo"), _course("Aprobado")
    for course in (nuevo, viejo, aprobado):
        await uow.golf_courses.save(course)
    await uow.hole_maps.save(_map(nuevo.id, imported_at=IMPORTADO + timedelta(days=1)))
    await uow.hole_maps.save(_map(viejo.id, holes=(1,)))
    ya = _map(aprobado.id)
    ya.approve(reviewer_id=ADMIN)
    await uow.hole_maps.save(ya)

    pending = await ListPendingHoleMapsUseCase(uow).execute()

    assert [p.golf_course_name for p in pending] == ["Viejo", "Nuevo"]
    assert pending[0].holes == 1
    assert pending[0].holes_needing_green == 1
    assert pending[0].imported_at == IMPORTADO
    assert pending[0].osm_reference == "way/1"
    assert pending[0].golf_course_id == str(viejo.id)


@pytest.mark.asyncio
@pytest.mark.parametrize("status", list(HoleMapStatus))
async def test_a2_admin_sees_the_map_in_any_status(status):
    """
    GIVEN: Un mapa en cualquier estado
    WHEN: El admin lo pide para revisarlo
    THEN: Sale con su estado, su referencia y los datos de la revisión
    """
    uow, course, hole_map = await _setup(status)

    dto = await GetHoleMapForReviewUseCase(uow).execute(str(course.id))

    assert dto.status == status.value
    assert dto.osm_reference == "way/1"
    assert dto.reviewed_at == hole_map.reviewed_at


@pytest.mark.asyncio
async def test_a2_review_of_missing_map_is_not_found():
    """
    GIVEN: Un campo sin mapa
    WHEN: El admin lo pide para revisarlo
    THEN: No se encuentra
    """
    with pytest.raises(HoleMapNotFoundError):
        await GetHoleMapForReviewUseCase(InMemoryGolfCourseUnitOfWork()).execute(
            str(GolfCourseId.generate())
        )


# ============================================================================
# A3-A8 — Aprobar y rechazar la versión vista
# ============================================================================


@pytest.mark.asyncio
async def test_a3_approve_the_seen_version():
    """
    GIVEN: Un mapa pendiente
    WHEN: El admin lo aprueba con la versión que vio
    THEN: Queda aprobado, con él como revisor
    """
    uow, course, hole_map = await _setup()

    dto = await ApproveHoleMapUseCase(uow).execute(
        str(course.id), ADMIN, ReviewHoleMapRequestDTO(version=IMPORTADO)
    )

    assert dto.status == "APPROVED"
    assert hole_map.status is HoleMapStatus.APPROVED
    assert hole_map.reviewed_by == ADMIN
    assert uow.committed is True


@pytest.mark.asyncio
async def test_a3_version_with_time_zone_is_the_same_moment():
    """
    GIVEN: La versión enviada con zona (UTC+2), el mismo instante que la importación
    WHEN: El admin aprueba
    THEN: Se acepta
    """
    uow, course, hole_map = await _setup()
    madrid = IMPORTADO.replace(tzinfo=UTC).astimezone(timezone(timedelta(hours=2)))

    await ApproveHoleMapUseCase(uow).execute(
        str(course.id), ADMIN, ReviewHoleMapRequestDTO(version=madrid)
    )

    assert hole_map.status is HoleMapStatus.APPROVED


@pytest.mark.asyncio
@pytest.mark.parametrize("use_case", [ApproveHoleMapUseCase, RejectHoleMapUseCase])
async def test_a4_other_version_changes_nothing(use_case):
    """
    GIVEN: Un mapa que se reimportó mientras el admin miraba otra versión
    WHEN: Aprueba o rechaza con la versión vieja
    THEN: «El mapa ha cambiado» y sigue pendiente
    """
    uow, course, hole_map = await _setup()

    with pytest.raises(HoleMapChangedError):
        await use_case(uow).execute(
            str(course.id),
            ADMIN,
            ReviewHoleMapRequestDTO(version=IMPORTADO - timedelta(microseconds=1)),
        )

    assert hole_map.status is HoleMapStatus.PENDING_REVIEW


@pytest.mark.asyncio
@pytest.mark.parametrize("use_case", [ApproveHoleMapUseCase, RejectHoleMapUseCase])
@pytest.mark.parametrize("status", [HoleMapStatus.APPROVED, HoleMapStatus.REJECTED])
async def test_a5_reviewed_map_is_not_pending(use_case, status):
    """
    GIVEN: Un mapa ya aprobado o rechazado
    WHEN: Se intenta revisar otra vez (con su versión)
    THEN: «No está pendiente»
    """
    uow, course, _ = await _setup(status)

    with pytest.raises(HoleMapNotPendingError):
        await use_case(uow).execute(
            str(course.id), ADMIN, ReviewHoleMapRequestDTO(version=IMPORTADO)
        )


@pytest.mark.asyncio
@pytest.mark.parametrize("reason", ["Los greens del 10 al 18 son de otro campo", None])
async def test_a6_reject_with_or_without_reason(reason):
    """
    GIVEN: Un mapa pendiente
    WHEN: El admin lo rechaza, con motivo o sin él
    THEN: Queda rechazado con ese motivo
    """
    uow, course, hole_map = await _setup()

    dto = await RejectHoleMapUseCase(uow).execute(
        str(course.id), ADMIN, ReviewHoleMapRequestDTO(version=IMPORTADO, reason=reason)
    )

    assert dto.status == "REJECTED"
    assert hole_map.rejection_reason == reason
    assert dto.rejection_reason == reason


@pytest.mark.asyncio
async def test_a6_reason_too_long_is_rejected():
    """
    GIVEN: Un motivo de 501 caracteres
    WHEN: Se rechaza el mapa
    THEN: Error de dato y el mapa sigue pendiente
    """
    uow, course, hole_map = await _setup()

    with pytest.raises(ValueError, match="500"):
        await RejectHoleMapUseCase(uow).execute(
            str(course.id), ADMIN, ReviewHoleMapRequestDTO(version=IMPORTADO, reason="x" * 501)
        )

    assert hole_map.status is HoleMapStatus.PENDING_REVIEW


@pytest.mark.asyncio
@pytest.mark.parametrize("use_case", [ApproveHoleMapUseCase, RejectHoleMapUseCase])
async def test_a7_review_of_missing_map_is_not_found(use_case):
    """
    GIVEN: Un campo sin mapa
    WHEN: Se aprueba o rechaza
    THEN: No se encuentra
    """
    with pytest.raises(HoleMapNotFoundError):
        await use_case(InMemoryGolfCourseUnitOfWork()).execute(
            str(GolfCourseId.generate()), ADMIN, ReviewHoleMapRequestDTO(version=IMPORTADO)
        )


@pytest.mark.asyncio
@pytest.mark.parametrize("use_case", [ApproveHoleMapUseCase, RejectHoleMapUseCase])
async def test_a8_review_reads_the_map_locked(use_case):
    """
    GIVEN: Un mapa pendiente
    WHEN: Se aprueba o rechaza
    THEN: Se lee con bloqueo (lo último de la BD), no con la lectura normal
    """
    uow, course, _ = await _setup()
    lecturas = []
    original = uow.hole_maps.find_by_golf_course_id_for_update

    async def espia(golf_course_id):
        lecturas.append("for_update")
        return await original(golf_course_id)

    uow.hole_maps.find_by_golf_course_id_for_update = espia

    await use_case(uow).execute(str(course.id), ADMIN, ReviewHoleMapRequestDTO(version=IMPORTADO))

    assert lecturas == ["for_update"]


@pytest.mark.asyncio
async def test_a1_pending_list_reads_course_names_in_one_query():
    """
    GIVEN: Tres mapas pendientes
    WHEN: El admin pide los pendientes
    THEN: Los nombres salen de una sola consulta, sin cargar cada campo entero
    """
    uow = InMemoryGolfCourseUnitOfWork()
    for name in ("Campo A", "Campo B", "Campo C"):
        course = _course(name)
        await uow.golf_courses.save(course)
        await uow.hole_maps.save(_map(course.id))

    async def no_cargar(_id):
        raise AssertionError("no se carga el campo entero para sacar su nombre")

    uow.golf_courses.find_by_id = no_cargar

    pending = await ListPendingHoleMapsUseCase(uow).execute()

    assert sorted(p.golf_course_name for p in pending) == ["Campo A", "Campo B", "Campo C"]
