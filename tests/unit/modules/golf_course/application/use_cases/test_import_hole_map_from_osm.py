"""
Tests del caso de uso que importa de OpenStreetMap el mapa de hoyos de un campo (BE #532).

La fuente de OSM es falsa: aquí se prueba lo que decide el caso de uso (qué
campos se importan, crear o reimportar, no pisar un mapa aprobado, ir en seco),
no el emparejado, que tiene sus propios tests.
"""

from datetime import datetime

import pytest

from src.modules.golf_course.application.dtos.hole_map_import_dtos import (
    ImportHoleMapRequestDTO,
    ImportHoleMapStatus,
)
from src.modules.golf_course.application.ports.osm_hole_map_source import (
    CardHole,
    DiscardReason,
    IOsmHoleMapSource,
    OsmHoleMapCandidate,
    OsmUnavailableError,
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
VALDERRAMA = CourseLocation(latitude=36.2858, longitude=-5.3247)


def _hole(number: int) -> MappedHole:
    return MappedHole(
        number=number,
        play_line=(
            GeoPoint(latitude=36.28, longitude=-5.33),
            GeoPoint(latitude=36.29, longitude=-5.33),
        ),
        line_source=PositionSource.OSM,
    )


CANDIDATO = OsmHoleMapCandidate(
    osm_reference="way/237391513",
    holes=(_hole(1), _hole(2)),
    discarded={DiscardReason.PAR_MISMATCH: 1, DiscardReason.NO_NUMBER: 2},
)


class FuenteFalsa(IOsmHoleMapSource):
    """Devuelve lo que se le diga y apunta con qué se la llamó."""

    def __init__(self, resultado=CANDIDATO):
        self.resultado = resultado
        self.llamadas: list[dict] = []

    async def find(self, *, latitude, longitude, card, physical_holes):
        self.llamadas.append(
            {
                "latitude": latitude,
                "longitude": longitude,
                "card": card,
                "physical_holes": physical_holes,
            }
        )
        if isinstance(self.resultado, Exception):
            raise self.resultado
        return self.resultado


def _course(location=VALDERRAMA, approved=True, physical_holes=None) -> GolfCourse:
    course = GolfCourse.create(
        name="Club de Golf Valderrama",
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
        location=location,
        physical_holes=physical_holes,
    )
    if approved:
        course.approve()
    return course


async def _setup(course=None, existing_map=None, fuente=None):
    uow = InMemoryGolfCourseUnitOfWork()
    course = course or _course()
    await uow.golf_courses.save(course)
    if existing_map is not None:
        await uow.hole_maps.save(existing_map)
    fuente = fuente or FuenteFalsa()
    return uow, course, fuente, ImportHoleMapFromOsmUseCase(uow, fuente)


def _existing(course_id: GolfCourseId) -> CourseHoleMap:
    return CourseHoleMap.create(
        golf_course_id=course_id,
        holes=[_hole(9)],
        osm_reference="way/1",
        imported_at=datetime(2026, 10, 1, 9, 0),
    )


def _request(course, apply=True):
    return ImportHoleMapRequestDTO(golf_course_id=str(course.id), apply=apply)


# ============================================================================
# U1-U2 — Qué campos se importan
# ============================================================================


@pytest.mark.asyncio
async def test_u1_course_without_coordinates_is_not_asked_to_osm():
    """
    GIVEN: Un campo aprobado sin coordenadas
    WHEN: Se importa su mapa
    THEN: «Sin coordenadas», sin pedir nada a OSM
    """
    uow, course, fuente, use_case = await _setup(course=_course(location=None))

    result = await use_case.execute(_request(course))

    assert result.status is ImportHoleMapStatus.NO_COORDINATES
    assert fuente.llamadas == []
    assert await uow.hole_maps.find_by_golf_course_id(course.id) is None


@pytest.mark.asyncio
async def test_u2_unknown_course_is_rejected():
    """
    GIVEN: Un id que no es de ningún campo
    WHEN: Se importa su mapa
    THEN: Se rechaza
    """
    _, _, fuente, use_case = await _setup()

    with pytest.raises(ValueError, match="not found"):
        await use_case.execute(ImportHoleMapRequestDTO(golf_course_id=str(GolfCourseId.generate())))

    assert fuente.llamadas == []


@pytest.mark.asyncio
async def test_u2_not_approved_course_is_rejected():
    """
    GIVEN: Un campo pendiente de aprobar
    WHEN: Se importa su mapa
    THEN: Se rechaza, sin pedir nada a OSM
    """
    _, course, fuente, use_case = await _setup(course=_course(approved=False))

    with pytest.raises(ValueError, match="approved"):
        await use_case.execute(_request(course))

    assert fuente.llamadas == []


# ============================================================================
# U3-U5 — Crear, reimportar, no pisar lo aprobado
# ============================================================================


@pytest.mark.asyncio
async def test_u3_creates_a_pending_map():
    """
    GIVEN: Un campo sin mapa y un candidato de OSM con dos hoyos
    WHEN: Se importa
    THEN: Se crea el mapa pendiente de revisión, con su referencia y sus hoyos
    """
    uow, course, _, use_case = await _setup()

    result = await use_case.execute(_request(course))

    assert result.status is ImportHoleMapStatus.CREATED
    saved = await uow.hole_maps.find_by_golf_course_id(course.id)
    assert saved is not None
    assert saved.status is HoleMapStatus.PENDING_REVIEW
    assert saved.osm_reference == "way/237391513"
    assert [h.number for h in saved.holes] == [1, 2]
    assert uow.committed is True


@pytest.mark.asyncio
async def test_u3_asks_osm_with_the_course_location_and_card():
    """
    GIVEN: Un campo de 9 hoyos sobre el terreno
    WHEN: Se importa
    THEN: A OSM se le pasa su coordenada, su tarjeta (par y hándicap) y sus 9 hoyos
    """
    _, course, fuente, use_case = await _setup(course=_course(physical_holes=9))

    await use_case.execute(_request(course))

    (llamada,) = fuente.llamadas
    assert (llamada["latitude"], llamada["longitude"]) == (36.2858, -5.3247)
    assert llamada["physical_holes"] == 9
    assert llamada["card"][0] == CardHole(number=1, par=4, stroke_index=1)
    assert len(llamada["card"]) == 18


@pytest.mark.asyncio
async def test_u3_course_without_physical_holes_is_taken_as_18():
    """
    GIVEN: Un campo sin hoyos sobre el terreno declarados
    WHEN: Se importa
    THEN: Se toma como de 18
    """
    _, course, fuente, use_case = await _setup(course=_course(physical_holes=None))

    await use_case.execute(_request(course))

    assert fuente.llamadas[0]["physical_holes"] == 18


@pytest.mark.asyncio
@pytest.mark.parametrize("rejected", [False, True], ids=["pendiente", "rechazado"])
async def test_u4_pending_or_rejected_map_is_reimported(rejected):
    """
    GIVEN: Un campo con mapa pendiente o rechazado
    WHEN: Se importa
    THEN: Se reimporta: los hoyos nuevos y pendiente de revisión
    """
    course = _course()
    existing = _existing(course.id)
    if rejected:
        existing.reject(reviewer_id=UserId.generate(), reason="Otro recorrido")
    uow, _, _, use_case = await _setup(course=course, existing_map=existing)

    result = await use_case.execute(_request(course))

    assert result.status is ImportHoleMapStatus.REIMPORTED
    saved = await uow.hole_maps.find_by_golf_course_id(course.id)
    assert saved is existing
    assert [h.number for h in saved.holes] == [1, 2]
    assert saved.status is HoleMapStatus.PENDING_REVIEW


@pytest.mark.asyncio
async def test_u5_approved_map_is_skipped_without_asking_osm():
    """
    GIVEN: Un campo con el mapa ya aprobado
    WHEN: Se importa
    THEN: Se salta («ya aprobado»), sin pedir nada a OSM ni tocar el mapa
    """
    course = _course()
    existing = _existing(course.id)
    existing.approve(reviewer_id=UserId.generate())
    _, _, fuente, use_case = await _setup(course=course, existing_map=existing)

    result = await use_case.execute(_request(course))

    assert result.status is ImportHoleMapStatus.SKIPPED_APPROVED
    assert fuente.llamadas == []
    assert [h.number for h in existing.holes] == [9]


# ============================================================================
# U6-U8 — Sin contorno, sin hoyos, OSM caído, recuento
# ============================================================================


@pytest.mark.asyncio
async def test_u6_no_outline_in_osm():
    """
    GIVEN: OSM no tiene contorno cerca del campo
    WHEN: Se importa
    THEN: «Sin contorno», sin crear mapa
    """
    uow, course, _, use_case = await _setup(fuente=FuenteFalsa(resultado=None))

    result = await use_case.execute(_request(course))

    assert result.status is ImportHoleMapStatus.NO_OUTLINE
    assert await uow.hole_maps.find_by_golf_course_id(course.id) is None


@pytest.mark.asyncio
async def test_u6_no_valid_holes():
    """
    GIVEN: Un contorno sin ningún hoyo que valga
    WHEN: Se importa
    THEN: «Sin hoyos válidos», sin crear mapa, pero con lo descartado
    """
    vacio = OsmHoleMapCandidate(
        osm_reference="way/5", holes=(), discarded={DiscardReason.PAR_MISMATCH: 3}
    )
    uow, course, _, use_case = await _setup(fuente=FuenteFalsa(resultado=vacio))

    result = await use_case.execute(_request(course))

    assert result.status is ImportHoleMapStatus.NO_VALID_HOLES
    assert result.discarded == {"PAR_MISMATCH": 3}
    assert await uow.hole_maps.find_by_golf_course_id(course.id) is None


@pytest.mark.asyncio
async def test_u6_no_valid_holes_leaves_an_existing_map_alone():
    """
    GIVEN: Un mapa pendiente y una reimportación sin hoyos válidos
    WHEN: Se importa
    THEN: El mapa que había no cambia
    """
    course = _course()
    existing = _existing(course.id)
    vacio = OsmHoleMapCandidate(osm_reference="way/5", holes=(), discarded={})
    _, _, _, use_case = await _setup(
        course=course, existing_map=existing, fuente=FuenteFalsa(resultado=vacio)
    )

    result = await use_case.execute(_request(course))

    assert result.status is ImportHoleMapStatus.NO_VALID_HOLES
    assert [h.number for h in existing.holes] == [9]


@pytest.mark.asyncio
async def test_u7_osm_unavailable_touches_nothing():
    """
    GIVEN: OSM no está disponible
    WHEN: Se importa
    THEN: «OSM no disponible», sin crear mapa
    """
    uow, course, _, use_case = await _setup(
        fuente=FuenteFalsa(resultado=OsmUnavailableError("Overpass 504"))
    )

    result = await use_case.execute(_request(course))

    assert result.status is ImportHoleMapStatus.OSM_UNAVAILABLE
    assert await uow.hole_maps.find_by_golf_course_id(course.id) is None


@pytest.mark.asyncio
async def test_u8_result_counts_imported_and_discarded_holes():
    """
    GIVEN: Un candidato con dos hoyos y tres descartados
    WHEN: Se importa
    THEN: El resultado dice cuántos entraron, cuántos quedaron fuera por motivo
         y la referencia OSM
    """
    _, course, _, use_case = await _setup()

    result = await use_case.execute(_request(course))

    assert result.holes_imported == 2
    assert result.discarded == {"PAR_MISMATCH": 1, "NO_NUMBER": 2}
    assert result.osm_reference == "way/237391513"


# ============================================================================
# S2 — En seco
# ============================================================================


@pytest.mark.asyncio
async def test_s2_dry_run_creates_nothing():
    """
    GIVEN: Un campo sin mapa
    WHEN: Se importa en seco (sin --apply)
    THEN: Dice que lo crearía, pero no guarda nada
    """
    uow, course, _, use_case = await _setup()

    result = await use_case.execute(_request(course, apply=False))

    assert result.status is ImportHoleMapStatus.CREATED
    assert result.holes_imported == 2
    assert await uow.hole_maps.find_by_golf_course_id(course.id) is None


@pytest.mark.asyncio
async def test_s2_dry_run_does_not_touch_an_existing_map():
    """
    GIVEN: Un mapa rechazado
    WHEN: Se importa en seco
    THEN: Dice que lo reimportaría, pero el mapa sigue igual y rechazado
    """
    course = _course()
    existing = _existing(course.id)
    existing.reject(reviewer_id=UserId.generate())
    _, _, _, use_case = await _setup(course=course, existing_map=existing)

    result = await use_case.execute(_request(course, apply=False))

    assert result.status is ImportHoleMapStatus.REIMPORTED
    assert existing.status is HoleMapStatus.REJECTED
    assert [h.number for h in existing.holes] == [9]
