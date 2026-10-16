"""
Tests de los casos de uso de las muestras anónimas de hoyo (BE #532, 16 oct 2026).

Por hoyo se guardan solo las tres primeras muestras que llegan; de la cuarta en
adelante se responde igual y no se guarda nada, y una muestra que el dominio
rechaza tampoco se guarda (ni se le dice al jugador). Vale para cualquier hoyo,
tenga o no datos en el mapa: las muestras enriquecen los codos.

| Caso                                                | Resultado                                  |
|-----------------------------------------------------|--------------------------------------------|
| Primera muestra con codos                           | Se guarda con sus codos                    |
| Segunda y tercera                                   | Se guardan                                 |
| Cuarta                                              | No se guarda, sin error                    |
| La misma persona manda las tres                     | Cuentan las tres (no se guarda quién)      |
| El tope es por hoyo y por campo                     | Otro hoyo y otro campo siguen recogiendo   |
| Hoyo con mapa aprobado completo, o solo con salida  | Se guarda igual                            |
| Tres codos                                          | No se guarda, sin error                    |
| Green a 30 m o a 800 m                              | No se guarda, sin error                    |
| Un punto a más de 3 km del campo                    | No se guarda, sin error                    |
| Coordenada imposible (latitud 91)                   | No se guarda, sin error                    |
| Campo sin ubicación                                 | No se mira la distancia al campo           |
| Una rechazada no gasta hueco                        | Las tres buenas de después se guardan      |
| Campo que no existe, pendiente o rechazado          | GolfCourseNotFoundError (al mandar y leer) |
| Hoyo 0 o 19                                         | HoleNotInCourseError                       |
| Hoyo 10 en un campo de 9                            | Se guarda                                  |
| Lectura sin muestras                                | 18 hoyos, sin muestra y recogiendo         |
| Lectura con muestras                                | La primera es la más antigua               |
| Con tres                                            | Ya no recoge; con dos, sí                  |
| La lectura                                          | No dice cuántas hay ni de quién            |
"""

from datetime import datetime

import pytest

from src.modules.golf_course.application.dtos.hole_sample_dtos import (
    HoleSampleStatusDTO,
    ListHoleSamplesRequestDTO,
    PointDTO,
    SubmitHoleSampleRequestDTO,
)
from src.modules.golf_course.application.exceptions import (
    GolfCourseNotFoundError,
    HoleNotInCourseError,
)
from src.modules.golf_course.application.use_cases.hole_sample_use_cases import (
    ListHoleSamplesUseCase,
    SubmitHoleSampleUseCase,
)
from src.modules.golf_course.domain.entities.course_hole_map import CourseHoleMap
from src.modules.golf_course.domain.entities.golf_course import GolfCourse
from src.modules.golf_course.domain.entities.hole import Hole
from src.modules.golf_course.domain.entities.tee import Tee
from src.modules.golf_course.domain.value_objects.course_location import CourseLocation
from src.modules.golf_course.domain.value_objects.course_type import CourseType
from src.modules.golf_course.domain.value_objects.geo_point import GeoPoint
from src.modules.golf_course.domain.value_objects.golf_course_id import GolfCourseId
from src.modules.golf_course.domain.value_objects.green_position import GreenPosition
from src.modules.golf_course.domain.value_objects.mapped_hole import MappedHole
from src.modules.golf_course.domain.value_objects.position_source import PositionSource
from src.modules.golf_course.domain.value_objects.tee_color import TeeColor
from src.modules.golf_course.infrastructure.persistence.in_memory.in_memory_golf_course_unit_of_work import (
    InMemoryGolfCourseUnitOfWork,
)
from src.modules.user.domain.value_objects.user_id import UserId
from src.shared.domain.value_objects.country_code import CountryCode
from src.shared.domain.value_objects.gender import Gender

pytestmark = pytest.mark.asyncio

M_PER_DEGREE = 6_371_000.0 * 3.141592653589793 / 180
SALIDA = (36.28, -5.33)
GREEN = (36.28 + 300 / M_PER_DEGREE, -5.33)  # 300 m al norte de la salida
CODO = (36.2815, -5.331)
CODO_2 = (36.282, -5.3312)


def _p(point: tuple[float, float]) -> PointDTO:
    return PointDTO(latitude=point[0], longitude=point[1])


def _north(metres: float, of=SALIDA) -> tuple[float, float]:
    return (of[0] + metres / M_PER_DEGREE, of[1])


def _course(physical_holes=None, location=None, approved=True) -> GolfCourse:
    course = GolfCourse.create(
        name="Valderrama",
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
        holes=[Hole(number=i + 1, par=4, stroke_index=i + 1, meters=350) for i in range(18)],
        location=location,
        physical_holes=physical_holes,
    )
    if approved:
        course.approve()
    return course


async def _setup(**course_args):
    uow = InMemoryGolfCourseUnitOfWork()
    course = _course(**course_args)
    await uow.golf_courses.save(course)
    return uow, course


def _request(course, hole=1, tee=SALIDA, bends=(), green=GREEN):
    return SubmitHoleSampleRequestDTO(
        golf_course_id=str(course.id if hasattr(course, "id") else course),
        hole_number=hole,
        tee=_p(tee),
        bends=[_p(b) for b in bends],
        green_center=_p(green),
    )


async def _submit(uow, course, **kwargs) -> None:
    result = await SubmitHoleSampleUseCase(uow).execute(_request(course, **kwargs))
    assert result is None  # Siempre lo mismo: el jugador nunca nota nada


async def _read(uow, course) -> list[HoleSampleStatusDTO]:
    return await ListHoleSamplesUseCase(uow).execute(
        ListHoleSamplesRequestDTO(golf_course_id=str(course.id))
    )


async def _hole(uow, course, number=1) -> HoleSampleStatusDTO:
    return (await _read(uow, course))[number - 1]


async def _stored(uow, course, hole=1) -> int:
    return await uow.hole_samples.count_for_hole(course.id, hole)


# ============================================================================
# S1 — Las tres primeras, y nada más
# ============================================================================


async def test_s1_first_sample_is_stored_with_its_bends():
    """
    GIVEN: Un campo aprobado sin muestras
    WHEN: Llega una muestra del hoyo 3 con dos codos
    THEN: Se guarda, y es la primera del hoyo 3 con sus codos en orden
    """
    uow, course = await _setup()

    await _submit(uow, course, hole=3, bends=[CODO, CODO_2])

    hole = await _hole(uow, course, 3)
    assert hole.first_sample is not None
    assert hole.first_sample.tee == _p(SALIDA)
    assert hole.first_sample.bends == [_p(CODO), _p(CODO_2)]
    assert hole.first_sample.green_center == _p(GREEN)
    assert await _stored(uow, course, 3) == 1


async def test_s1_second_and_third_are_stored():
    """
    GIVEN: Una muestra guardada en el hoyo 1
    WHEN: Llegan la segunda y la tercera
    THEN: Hay tres guardadas
    """
    uow, course = await _setup()
    await _submit(uow, course)

    await _submit(uow, course, bends=[CODO])
    assert await _stored(uow, course) == 2
    await _submit(uow, course, green=_north(320))

    assert await _stored(uow, course) == 3


async def test_s1_the_fourth_is_not_stored_and_nothing_is_said():
    """
    GIVEN: Tres muestras guardadas en el hoyo 1
    WHEN: Llega la cuarta
    THEN: Se responde igual (sin error) y siguen siendo tres; la primera no cambia
    """
    uow, course = await _setup()
    for _ in range(3):
        await _submit(uow, course)

    await _submit(uow, course, bends=[CODO], green=_north(500))

    assert await _stored(uow, course) == 3
    assert (await _hole(uow, course)).first_sample.bends == []


async def test_s1_the_same_player_can_fill_all_three():
    """
    GIVEN: Un único jugador (no se guarda quién manda: no hay con qué distinguirlo)
    WHEN: Manda cinco veces el hoyo 2
    THEN: Cuentan las tres primeras, y el hoyo deja de recoger
    """
    uow, course = await _setup()

    for _ in range(5):
        await _submit(uow, course, hole=2)

    assert await _stored(uow, course, 2) == 3
    assert (await _hole(uow, course, 2)).collecting is False


async def test_s1_the_cap_is_per_hole_and_per_course():
    """
    GIVEN: El hoyo 1 de un campo con sus tres muestras
    WHEN: Llegan muestras del hoyo 2 del mismo campo y del hoyo 1 de otro campo
    THEN: Se guardan las dos
    """
    uow, course = await _setup()
    otro = _course()
    await uow.golf_courses.save(otro)
    for _ in range(3):
        await _submit(uow, course)

    await _submit(uow, course, hole=2)
    await _submit(uow, otro)

    assert await _stored(uow, course, 2) == 1
    assert await _stored(uow, otro, 1) == 1


@pytest.mark.parametrize("with_green", [True, False])
async def test_s1_holes_with_an_approved_map_take_samples_too(with_green):
    """
    GIVEN: Un mapa aprobado con el hoyo 1 completo (salida y green), o solo con salida
    WHEN: Llega una muestra del hoyo 1
    THEN: Se guarda: las muestras enriquecen los codos de cualquier hoyo
    """
    uow, course = await _setup()
    tee, green = GeoPoint(*SALIDA), GeoPoint(*GREEN)
    hole_map = CourseHoleMap.create(
        golf_course_id=course.id,
        holes=[
            MappedHole(
                number=1,
                play_line=(tee, green),
                line_source=PositionSource.OSM,
                green=GreenPosition(
                    front=green, center=green, back=green, source=PositionSource.OSM
                )
                if with_green
                else None,
            )
        ],
        osm_reference="way/1",
        imported_at=datetime(2026, 10, 15, 9, 0),
    )
    hole_map.approve(reviewer_id=UserId.generate())
    await uow.hole_maps.save(hole_map)

    await _submit(uow, course, bends=[CODO])

    assert await _stored(uow, course) == 1


# ============================================================================
# S2 — Lo que el dominio rechaza no se guarda, y no se dice
# ============================================================================


@pytest.mark.parametrize(
    "changes",
    [
        {"bends": [CODO, CODO_2, CODO]},
        {"green": _north(30)},
        {"green": _north(800)},
        {"tee": (91.0, -5.33)},
        {"green": (36.29, 181.0)},
        {"bends": [(-91.0, 0.0)]},
    ],
    ids=["three-bends", "30m", "800m", "lat-91", "lon-181", "bend-lat-91"],
)
async def test_s2_impossible_samples_are_dropped_silently(changes):
    """
    GIVEN: Tres codos, un green a 30 m o a 800 m, o una coordenada imposible
    WHEN: Llega la muestra
    THEN: No hay error y no se guarda nada; el hoyo sigue recogiendo
    """
    uow, course = await _setup()

    await _submit(uow, course, **changes)

    assert await _stored(uow, course) == 0
    hole = await _hole(uow, course)
    assert (hole.first_sample, hole.collecting) == (None, True)


async def test_s2_far_from_the_course_is_dropped_silently():
    """
    GIVEN: Un campo con ubicación a ~5,5 km de la muestra
    WHEN: Llega la muestra
    THEN: No hay error y no se guarda
    """
    uow, course = await _setup(location=CourseLocation(latitude=36.33, longitude=-5.33))

    await _submit(uow, course)

    assert await _stored(uow, course) == 0


async def test_s2_near_the_course_is_stored():
    """
    GIVEN: Un campo con ubicación a ~1 km de la muestra
    WHEN: Llega la muestra
    THEN: Se guarda
    """
    uow, course = await _setup(location=CourseLocation(latitude=36.29, longitude=-5.33))

    await _submit(uow, course, bends=[CODO])

    assert await _stored(uow, course) == 1


async def test_s2_without_course_location_the_distance_is_not_checked():
    """
    GIVEN: Un campo sin ubicación
    WHEN: Llega una muestra en Galicia (lejos de cualquier campo conocido)
    THEN: Se guarda: sin ubicación no hay con qué comparar
    """
    uow, course = await _setup(location=None)
    lejos = (43.0, -8.0)

    await _submit(uow, course, tee=lejos, green=_north(300, of=lejos))

    assert await _stored(uow, course) == 1


async def test_s2_a_dropped_sample_does_not_use_a_slot():
    """
    GIVEN: Una muestra imposible (tres codos) como primera en llegar
    WHEN: Llegan después tres buenas
    THEN: Se guardan las tres, y la primera del hoyo es la primera buena
    """
    uow, course = await _setup()
    await _submit(uow, course, bends=[CODO, CODO_2, CODO])

    await _submit(uow, course, bends=[CODO_2])
    await _submit(uow, course)
    await _submit(uow, course)

    assert await _stored(uow, course) == 3
    assert (await _hole(uow, course)).first_sample.bends == [_p(CODO_2)]


# ============================================================================
# S3 — Campo y hoyo
# ============================================================================


async def test_s3_unknown_course_is_not_found():
    """
    GIVEN: Un id que no es de ningún campo
    WHEN: Se manda una muestra o se leen
    THEN: GolfCourseNotFoundError en los dos
    """
    uow, _ = await _setup()
    nadie = GolfCourseId.generate()

    with pytest.raises(GolfCourseNotFoundError):
        await SubmitHoleSampleUseCase(uow).execute(_request(nadie))
    with pytest.raises(GolfCourseNotFoundError):
        await ListHoleSamplesUseCase(uow).execute(
            ListHoleSamplesRequestDTO(golf_course_id=str(nadie))
        )


@pytest.mark.parametrize("kind", ["pending", "rejected"])
async def test_s3_courses_players_cannot_see_are_not_found(kind):
    """
    GIVEN: Un campo pendiente de aprobar (como el clon de una propuesta) o uno rechazado
    WHEN: Se manda una muestra o se leen
    THEN: GolfCourseNotFoundError, y no se guarda nada
    """
    uow = InMemoryGolfCourseUnitOfWork()
    course = _course(approved=False)
    if kind == "rejected":
        course.reject("El campo no existe en la realidad")
    await uow.golf_courses.save(course)

    with pytest.raises(GolfCourseNotFoundError):
        await SubmitHoleSampleUseCase(uow).execute(_request(course))
    with pytest.raises(GolfCourseNotFoundError):
        await _read(uow, course)
    assert await _stored(uow, course) == 0


@pytest.mark.parametrize("hole", [0, 19, -1])
async def test_s3_hole_outside_a_round(hole):
    """
    GIVEN: Un campo de 18
    WHEN: Llega una muestra del hoyo 0, 19 o -1
    THEN: HoleNotInCourseError
    """
    uow, course = await _setup()

    with pytest.raises(HoleNotInCourseError):
        await SubmitHoleSampleUseCase(uow).execute(_request(course, hole=hole))


async def test_s3_the_hole_is_checked_before_the_sample():
    """
    GIVEN: Una muestra imposible (tres codos) en el hoyo 19
    WHEN: Llega
    THEN: HoleNotInCourseError: el hoyo se mira antes que la geometría
    """
    uow, course = await _setup()

    with pytest.raises(HoleNotInCourseError):
        await SubmitHoleSampleUseCase(uow).execute(
            _request(course, hole=19, bends=[CODO, CODO_2, CODO])
        )


@pytest.mark.parametrize(("physical_holes", "hole"), [(9, 10), (9, 18), (9, 1), (None, 18)])
async def test_s3_any_hole_of_the_round_is_fine_even_on_nine_holes(physical_holes, hole):
    """
    GIVEN: Un campo de 9 (se juega dos veces, y la segunda vuelta suele salir de
           otras salidas) o uno sin el dato
    WHEN: Llega una muestra de un hoyo del 1 al 18
    THEN: Se guarda
    """
    uow, course = await _setup(physical_holes=physical_holes)

    await _submit(uow, course, hole=hole)

    assert await _stored(uow, course, hole) == 1


# ============================================================================
# S4 — La lectura
# ============================================================================


async def test_s4_without_samples_there_are_eighteen_empty_holes():
    """
    GIVEN: Un campo sin muestras
    WHEN: Se leen
    THEN: 18 hoyos, del 1 al 18, sin muestra y recogiendo
    """
    uow, course = await _setup()

    holes = await _read(uow, course)

    assert [h.hole_number for h in holes] == list(range(1, 19))
    assert all(h.first_sample is None and h.collecting is True for h in holes)


async def test_s4_first_sample_is_the_oldest():
    """
    GIVEN: Tres muestras del hoyo 5 que llegan una detrás de otra (codo A, codo B, sin codo)
    WHEN: Se leen
    THEN: La primera del hoyo 5 es la del codo A
    """
    uow, course = await _setup()
    await _submit(uow, course, hole=5, bends=[CODO])
    await _submit(uow, course, hole=5, bends=[CODO_2])
    await _submit(uow, course, hole=5)

    assert (await _hole(uow, course, 5)).first_sample.bends == [_p(CODO)]


async def test_s4_collecting_until_three():
    """
    GIVEN: El hoyo 1 con dos muestras y el 2 con tres
    WHEN: Se leen
    THEN: El 1 sigue recogiendo; el 2, no
    """
    uow, course = await _setup()
    for _ in range(2):
        await _submit(uow, course, hole=1)
    for _ in range(3):
        await _submit(uow, course, hole=2)

    holes = await _read(uow, course)

    assert (holes[0].collecting, holes[1].collecting) == (True, False)


async def test_s4_only_that_course():
    """
    GIVEN: Una muestra del hoyo 1 en otro campo
    WHEN: Se leen las de este
    THEN: Su hoyo 1 no tiene muestra
    """
    uow, course = await _setup()
    otro = _course()
    await uow.golf_courses.save(otro)
    await _submit(uow, otro)

    assert (await _hole(uow, course)).first_sample is None


async def test_s4_the_read_does_not_say_how_many_or_who():
    """
    GIVEN: Un hoyo con dos muestras
    WHEN: Se lee
    THEN: Solo trae el número de hoyo, la primera muestra (salida, codos, green) y si recoge
    """
    uow, course = await _setup()
    await _submit(uow, course)
    await _submit(uow, course)

    hole = (await _hole(uow, course)).model_dump()

    assert set(hole) == {"hole_number", "first_sample", "collecting"}
    assert set(hole["first_sample"]) == {"tee", "bends", "green_center"}
