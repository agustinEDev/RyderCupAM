"""
Tests del listado de campos aprobados: búsqueda, paginación y cercanía.

Se apoyan en el repositorio en memoria en vez de en un mock para que el doble
aplique de verdad los filtros: un mock devolvería lo que se le diga y daría por
buena una consulta que en producción devuelve otra cosa.
"""

from uuid import uuid4

import pytest
from pydantic import ValidationError

from src.modules.golf_course.application.dtos.golf_course_dtos import (
    ListApprovedGolfCoursesRequestDTO,
)
from src.modules.golf_course.application.use_cases.list_approved_golf_courses_use_case import (
    ListApprovedGolfCoursesUseCase,
)
from src.modules.golf_course.domain.entities.golf_course import GolfCourse
from src.modules.golf_course.domain.entities.hole import Hole
from src.modules.golf_course.domain.entities.tee import Tee
from src.modules.golf_course.domain.value_objects.course_location import CourseLocation
from src.modules.golf_course.domain.value_objects.course_type import CourseType
from src.modules.golf_course.domain.value_objects.tee_color import TeeColor
from src.modules.golf_course.infrastructure.persistence.in_memory.in_memory_golf_course_repository import (
    InMemoryGolfCourseRepository,
)
from src.modules.user.domain.value_objects.user_id import UserId
from src.shared.domain.value_objects.country_code import CountryCode
from src.shared.domain.value_objects.gender import Gender

# Coordenadas reales, para poder comprobar las distancias a mano
MADRID = (40.4168, -3.7038)
NEAR_MADRID = (40.45, -3.68)  # unos 4 km
TOLEDO = (39.8628, -4.0273)  # unos 65 km
BARCELONA = (41.3874, 2.1686)  # unos 500 km


class FakeUnitOfWork:
    """Unit of Work mínimo sobre el repositorio en memoria."""

    def __init__(self) -> None:
        self.golf_courses = InMemoryGolfCourseRepository()

    async def __aenter__(self) -> "FakeUnitOfWork":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        return None


def build_tees() -> list[Tee]:
    """Dos salidas válidas, suficientes para el invariante del campo."""
    return [
        Tee(
            color=TeeColor.WHITE,
            gender=Gender.MALE,
            identifier="Blanco",
            course_rating=73.5,
            slope_rating=135,
        ),
        Tee(
            color=TeeColor.YELLOW,
            gender=Gender.MALE,
            identifier="Amarillo",
            course_rating=71.2,
            slope_rating=128,
        ),
    ]


def build_holes() -> list[Hole]:
    """Dieciocho hoyos con stroke index correlativo."""
    return [Hole(number=i, par=4, stroke_index=i) for i in range(1, 19)]


async def add_course(uow: FakeUnitOfWork, name: str, coordinates=None) -> GolfCourse:
    """Guarda un campo aprobado, opcionalmente situado."""
    location = (
        CourseLocation(latitude=coordinates[0], longitude=coordinates[1]) if coordinates else None
    )
    course = GolfCourse.create(
        name=name,
        country_code=CountryCode("ES"),
        course_type=CourseType.STANDARD_18,
        creator_id=UserId(str(uuid4())),
        tees=build_tees(),
        holes=build_holes(),
        location=location,
    )
    course.approve()
    await uow.golf_courses.save(course)
    return course


@pytest.fixture
def uow() -> FakeUnitOfWork:
    """Unit of Work en memoria, vacío."""
    return FakeUnitOfWork()


# ============================================================================
# Tests: el DTO de listado no lleva tarjeta
# ============================================================================


@pytest.mark.asyncio
async def test_the_listing_leaves_out_the_scorecard(uow):
    """
    GIVEN: Un campo aprobado con sus 18 hoyos
    WHEN: Se lista
    THEN: El resultado no trae la tarjeta, pero sí las salidas y el par total

    Es el motivo de todo el cambio: 802 campos por 18 hoyos son 14.436 objetos
    que viajaban para pintar una lista de nombres. Las salidas se quedan porque
    el panel de administración dibuja una insignia por cada una.
    """
    await add_course(uow, "Club de Campo")
    use_case = ListApprovedGolfCoursesUseCase(uow)

    response = await use_case.execute(ListApprovedGolfCoursesRequestDTO())

    listed = response.golf_courses[0]
    assert not hasattr(listed, "holes")
    assert len(listed.tees) == 2
    assert listed.tees[0].holes is None
    assert listed.total_par == 72
    assert listed.distance_km is None


# ============================================================================
# Tests: búsqueda por nombre
# ============================================================================


@pytest.mark.asyncio
async def test_searching_by_name_ignores_case(uow):
    """
    GIVEN: Campos con nombres distintos
    WHEN: Se busca un trozo del nombre en minúsculas
    THEN: Salen los que lo contienen, sea cual sea su capitalización
    """
    await add_course(uow, "Real Club de La Moraleja")
    await add_course(uow, "Club de Campo")
    await add_course(uow, "Golf Santander")
    use_case = ListApprovedGolfCoursesUseCase(uow)

    response = await use_case.execute(ListApprovedGolfCoursesRequestDTO(name="club"))

    assert response.total == 2
    assert {course.name for course in response.golf_courses} == {
        "Real Club de La Moraleja",
        "Club de Campo",
    }


# ============================================================================
# Tests: paginación
# ============================================================================


@pytest.mark.asyncio
async def test_the_page_reports_how_many_there_are_in_total(uow):
    """
    GIVEN: Tres campos aprobados
    WHEN: Se pide una página de dos
    THEN: Vienen dos, pero el total sigue siendo tres

    Sin el total, el cliente no puede saber si merece la pena pedir más.
    """
    for index in range(3):
        await add_course(uow, f"Campo {index}")
    use_case = ListApprovedGolfCoursesUseCase(uow)

    response = await use_case.execute(ListApprovedGolfCoursesRequestDTO(limit=2))

    assert response.count == 2
    assert response.total == 3


@pytest.mark.asyncio
async def test_without_a_limit_everything_comes_back(uow):
    """
    GIVEN: Tres campos aprobados
    WHEN: Se lista sin pedir límite
    THEN: Vienen los tres

    El límite es opcional a propósito: un cliente que no pagine no debe dejar
    de ver campos porque el servidor haya cambiado.
    """
    for index in range(3):
        await add_course(uow, f"Campo {index}")
    use_case = ListApprovedGolfCoursesUseCase(uow)

    response = await use_case.execute(ListApprovedGolfCoursesRequestDTO())

    assert response.count == 3
    assert response.total == 3


# ============================================================================
# Tests: cercanía
# ============================================================================


@pytest.mark.asyncio
async def test_courses_come_back_nearest_first_with_their_distance(uow):
    """
    GIVEN: Tres campos a 4, 65 y 500 km de Madrid
    WHEN: Se busca desde Madrid
    THEN: Salen de más cerca a más lejos, cada uno con su distancia
    """
    await add_course(uow, "Campo de Barcelona", BARCELONA)
    await add_course(uow, "Campo de Madrid", NEAR_MADRID)
    await add_course(uow, "Campo de Toledo", TOLEDO)
    use_case = ListApprovedGolfCoursesUseCase(uow)

    response = await use_case.execute(
        ListApprovedGolfCoursesRequestDTO(latitude=MADRID[0], longitude=MADRID[1])
    )

    assert [course.name for course in response.golf_courses] == [
        "Campo de Madrid",
        "Campo de Toledo",
        "Campo de Barcelona",
    ]
    distances = [course.distance_km for course in response.golf_courses]
    assert distances[0] < 10
    assert 50 < distances[1] < 80
    assert 400 < distances[2] < 600


@pytest.mark.asyncio
async def test_the_radius_leaves_out_what_is_too_far(uow):
    """
    GIVEN: Campos a 4, 65 y 500 km
    WHEN: Se busca en un radio de 100 km
    THEN: Solo salen los dos primeros, y el total cuenta solo esos
    """
    await add_course(uow, "Campo de Madrid", NEAR_MADRID)
    await add_course(uow, "Campo de Toledo", TOLEDO)
    await add_course(uow, "Campo de Barcelona", BARCELONA)
    use_case = ListApprovedGolfCoursesUseCase(uow)

    response = await use_case.execute(
        ListApprovedGolfCoursesRequestDTO(latitude=MADRID[0], longitude=MADRID[1], radius_km=100)
    )

    assert response.total == 2
    assert {course.name for course in response.golf_courses} == {
        "Campo de Madrid",
        "Campo de Toledo",
    }


@pytest.mark.asyncio
async def test_a_course_without_coordinates_is_left_out_of_a_nearby_search(uow):
    """
    GIVEN: Un campo situado y otro sin coordenadas
    WHEN: Se busca por cercanía
    THEN: Solo sale el situado

    Doce de los 803 campos importados no tienen coordenadas. Ahí no hay
    distancia que enseñar, así que quedan fuera de este camino; la búsqueda por
    nombre sigue siendo el suyo.
    """
    await add_course(uow, "Campo situado", NEAR_MADRID)
    await add_course(uow, "Campo sin sitio")
    use_case = ListApprovedGolfCoursesUseCase(uow)

    response = await use_case.execute(
        ListApprovedGolfCoursesRequestDTO(latitude=MADRID[0], longitude=MADRID[1])
    )

    assert response.total == 1
    assert response.golf_courses[0].name == "Campo situado"


@pytest.mark.asyncio
async def test_a_course_without_coordinates_still_shows_up_by_name(uow):
    """
    GIVEN: Un campo sin coordenadas
    WHEN: Se busca por su nombre, sin posición
    THEN: Sale
    """
    await add_course(uow, "Campo sin sitio")
    use_case = ListApprovedGolfCoursesUseCase(uow)

    response = await use_case.execute(ListApprovedGolfCoursesRequestDTO(name="sin sitio"))

    assert response.total == 1


# ============================================================================
# Tests: coordenadas incompletas
# ============================================================================


def test_half_a_coordinate_is_rejected():
    """
    GIVEN: Una petición con latitud pero sin longitud
    WHEN: Se construye
    THEN: Falla

    Media coordenada no sitúa nada, y ordenar por una distancia calculada a
    partir de ella devolvería un orden arbitrario con pinta de correcto.
    """
    with pytest.raises(ValidationError, match="must be provided together"):
        ListApprovedGolfCoursesRequestDTO(latitude=40.4)


def test_a_radius_without_a_position_is_rejected():
    """
    GIVEN: Una petición con radio pero sin coordenadas
    WHEN: Se construye
    THEN: Falla, porque no hay desde dónde medir
    """
    with pytest.raises(ValidationError, match="requires latitude and longitude"):
        ListApprovedGolfCoursesRequestDTO(radius_km=50)


def test_the_limit_has_a_ceiling():
    """
    GIVEN: Una petición con un límite desmesurado
    WHEN: Se construye
    THEN: Falla

    El tope existe para que nadie pueda pedir el catálogo entero por accidente
    ahora que hay 802 campos.
    """
    with pytest.raises(ValidationError):
        ListApprovedGolfCoursesRequestDTO(limit=5000)
