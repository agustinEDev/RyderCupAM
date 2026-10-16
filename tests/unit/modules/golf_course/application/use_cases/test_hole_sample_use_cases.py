"""
Tests de los casos de uso de las muestras anónimas de hoyo (BE #532, 16 oct 2026).

Por hoyo se guardan solo las tres primeras muestras que llegan; de la cuarta en
adelante se responde igual y no se guarda nada, y una muestra que el dominio
rechaza tampoco se guarda (ni se le dice al jugador). Vale para cualquier hoyo,
tenga o no datos en el mapa: las muestras enriquecen los codos.

Revisión del 16 oct (Agustín): el id lo pone el móvil y una muestra repetida
cuenta una vez; cada jugador aporta como mucho una muestra por campo y hoyo
cada 10 minutos (en memoria, nunca en la BD ni en los logs), y solo gasta su
ventana una muestra que de verdad se guardó y se confirmó. Y todo va por barra
(color y género): cada una sale de un sitio distinto.

| Caso                                                | Resultado                                  |
|-----------------------------------------------------|--------------------------------------------|
| Primera muestra con codos                           | Se guarda con sus codos                    |
| Segunda y tercera                                   | Se guardan                                 |
| Cuarta                                              | No se guarda, sin error                    |
| La misma persona, cinco seguidas                    | Cuenta una (una cada 10 min por hoyo)      |
| La misma persona, cada 10 minutos                   | Llena las tres                             |
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
| Lectura sin muestras                                | 18 hoyos, sin barras                       |
| Lectura con muestras                                | La primera de cada barra es la más antigua |
| Con tres                                            | Esa barra ya no recoge; con dos, sí        |
| Varias barras en un hoyo                            | En el orden de su primera muestra          |
| La lectura                                          | No dice cuántas hay ni de quién            |
| 3 amarillas-hombre y 3 rojas-mujer                  | Se guardan las seis; la 4.ª amarilla, no   |
| Amarillas sin género                                | Otra barra distinta de amarillas-hombre    |
| Mismo jugador, otra barra del mismo hoyo            | Se guarda (la ventana es por barra)        |
| Barra que el campo no tiene                         | No se guarda, sin error, no gasta ventana  |
| Campo con amarillas sin género                      | Hombre y sin género, la misma barra        |
| La ventana y el cubo                                | Con la barra resuelta del campo            |
| Respuesta del caso de uso                           | Siempre SubmitHoleSampleResponseDTO vacío  |
| Mismo id dos veces                                  | Cuenta una                                 |
| Mismo id en otro hoyo                               | No se guarda (el id es único)              |
| Un id repetido no gasta hueco                       | Las nuevas de después llenan el hoyo       |
| Mismo jugador antes de 10 min (599 s)               | No se guarda, sin error                    |
| Mismo jugador a los 10 min                          | Se guarda                                  |
| Otro jugador, otro hoyo u otro campo                | No les afecta la ventana                   |
| Rechazada, repetida o con el hoyo lleno             | No abre la ventana del jugador             |
| Falla la transacción                                | No abre la ventana; el reintento se guarda |
| El log al descartar                                 | Sin coordenadas ni quién la mandó          |
"""

import logging
from datetime import datetime
from uuid import uuid4

import pytest

from src.modules.golf_course.application.dtos.hole_sample_dtos import (
    HoleSampleStatusDTO,
    ListHoleSamplesRequestDTO,
    ListHoleSamplesResponseDTO,
    PointDTO,
    SubmitHoleSampleRequestDTO,
    SubmitHoleSampleResponseDTO,
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
from src.modules.golf_course.infrastructure.services.in_memory_recent_hole_sample_senders import (
    InMemoryRecentHoleSampleSenders,
)
from src.modules.user.domain.value_objects.user_id import UserId
from src.shared.domain.value_objects.country_code import CountryCode
from src.shared.domain.value_objects.gender import Gender

pytestmark = pytest.mark.asyncio

JUGADOR = str(uuid4())
OTRO = str(uuid4())
M_PER_DEGREE = 6_371_000.0 * 3.141592653589793 / 180
SALIDA = (36.28, -5.33)
GREEN = (36.28 + 300 / M_PER_DEGREE, -5.33)  # 300 m al norte de la salida
CODO = (36.2815, -5.331)
CODO_2 = (36.282, -5.3312)


def _p(point: tuple[float, float]) -> PointDTO:
    return PointDTO(latitude=point[0], longitude=point[1])


def _north(metres: float, of=SALIDA) -> tuple[float, float]:
    return (of[0] + metres / M_PER_DEGREE, of[1])


def _tee(color: TeeColor, gender: Gender | None) -> Tee:
    return Tee(color=color, gender=gender, identifier=None, course_rating=71.2, slope_rating=128)


# Las barras del campo de prueba: amarillas de hombre, rojas de mujer y blancas sin género
BARRAS = ((TeeColor.YELLOW, Gender.MALE), (TeeColor.RED, Gender.FEMALE), (TeeColor.WHITE, None))


def _course(physical_holes=None, location=None, approved=True, tees=BARRAS) -> GolfCourse:
    course = GolfCourse.create(
        name="Valderrama",
        country_code=CountryCode("ES"),
        course_type=CourseType.STANDARD_18,
        creator_id=UserId.generate(),
        tees=[_tee(color, gender) for color, gender in tees],
        holes=[Hole(number=i + 1, par=4, stroke_index=i + 1, meters=350) for i in range(18)],
        location=location,
        physical_holes=physical_holes,
    )
    if approved:
        course.approve()
    return course


class Reloj:
    """Un reloj que solo avanza cuando el test lo pide (segundos, como time.monotonic)."""

    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


class UoWQueFallaAlConfirmar(InMemoryGolfCourseUnitOfWork):
    """La transacción falla al confirmar las veces que se pida (p. ej. la BD se cae)."""

    def __init__(self) -> None:
        super().__init__()
        self.failures = 0

    async def commit(self) -> None:
        if self.failures:
            self.failures -= 1
            raise RuntimeError("commit failed")
        await super().commit()


async def _setup(uow=None, **course_args):
    uow = uow or InMemoryGolfCourseUnitOfWork()
    uow.reloj = Reloj()
    uow.senders = InMemoryRecentHoleSampleSenders(clock=uow.reloj)
    course = _course(**course_args)
    await uow.golf_courses.save(course)
    return uow, course


def _use_case(uow) -> SubmitHoleSampleUseCase:
    return SubmitHoleSampleUseCase(uow, uow.senders)


def _request(
    course,
    hole=1,
    tee=SALIDA,
    bends=(),
    green=GREEN,
    user=None,
    sample_id=None,
    tee_color=TeeColor.YELLOW,
    tee_gender=Gender.MALE,
):
    """
    Sin `user`, cada envío es de un jugador distinto: la ventana de 10 min no se
    mete. Sin barra, amarillas de hombre.
    """
    return SubmitHoleSampleRequestDTO(
        id=sample_id or uuid4(),
        golf_course_id=str(course.id if hasattr(course, "id") else course),
        hole_number=hole,
        tee_color=tee_color,
        tee_gender=tee_gender,
        user_id=user or str(uuid4()),
        tee=_p(tee),
        bends=[_p(b) for b in bends],
        green_center=_p(green),
    )


async def _submit(uow, course, **kwargs) -> None:
    result = await _use_case(uow).execute(_request(course, **kwargs))
    # Siempre lo mismo: el jugador nunca nota nada
    assert result == SubmitHoleSampleResponseDTO()


async def _read(uow, course) -> list[HoleSampleStatusDTO]:
    response = await ListHoleSamplesUseCase(uow).execute(
        ListHoleSamplesRequestDTO(golf_course_id=str(course.id))
    )
    assert isinstance(response, ListHoleSamplesResponseDTO)
    return response.holes


async def _hole(uow, course, number=1) -> HoleSampleStatusDTO:
    return (await _read(uow, course))[number - 1]


async def _tee_of(uow, course, number=1, color=TeeColor.YELLOW, gender=Gender.MALE):
    """La barra del hoyo en la lectura; None si no tiene ninguna muestra."""
    hole = await _hole(uow, course, number)
    return next((t for t in hole.tees if (t.tee_color, t.tee_gender) == (color, gender)), None)


def _window_open(uow, course, color=TeeColor.YELLOW, gender=Gender.MALE) -> bool:
    """Si el jugador podría aportar ya a esa barra del hoyo 1 (sin dejarla reservada)."""
    key = (JUGADOR, course.id, 1, color, gender)
    if not uow.senders.reserve(*key):
        return False
    uow.senders.release(*key)
    return True


async def _stored(uow, course, hole=1, color=TeeColor.YELLOW, gender=Gender.MALE) -> int:
    return await uow.hole_samples.count_for_tee(course.id, hole, color, gender)


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

    hole = await _tee_of(uow, course, 3)
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
    assert (await _tee_of(uow, course)).first_sample.bends == []


async def test_s1_the_same_player_in_a_row_counts_once():
    """
    GIVEN: Un único jugador
    WHEN: Manda cinco veces seguidas el hoyo 2
    THEN: Cuenta una: como mucho una suya por hoyo cada 10 minutos
    """
    uow, course = await _setup()

    for _ in range(5):
        await _submit(uow, course, hole=2, user=JUGADOR)

    assert await _stored(uow, course, 2) == 1


async def test_s1_the_same_player_can_fill_all_three_every_ten_minutes():
    """
    GIVEN: Un único jugador (en la BD no se guarda quién manda)
    WHEN: Manda el hoyo 2 cinco veces, una cada 10 minutos
    THEN: Cuentan las tres primeras, y el hoyo deja de recoger
    """
    uow, course = await _setup()

    for _ in range(5):
        await _submit(uow, course, hole=2, user=JUGADOR)
        uow.reloj.advance(600)

    assert await _stored(uow, course, 2) == 3
    assert (await _tee_of(uow, course, 2)).collecting is False


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
    assert (await _hole(uow, course)).tees == []


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
    assert (await _tee_of(uow, course)).first_sample.bends == [_p(CODO_2)]


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
        await _use_case(uow).execute(_request(nadie))
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
    uow, course = await _setup(approved=False)
    if kind == "rejected":
        course.reject("El campo no existe en la realidad")
        await uow.golf_courses.save(course)

    with pytest.raises(GolfCourseNotFoundError):
        await _use_case(uow).execute(_request(course))
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
        await _use_case(uow).execute(_request(course, hole=hole))


async def test_s3_the_hole_is_checked_before_the_sample():
    """
    GIVEN: Una muestra imposible (tres codos) en el hoyo 19
    WHEN: Llega
    THEN: HoleNotInCourseError: el hoyo se mira antes que la geometría
    """
    uow, course = await _setup()

    with pytest.raises(HoleNotInCourseError):
        await _use_case(uow).execute(_request(course, hole=19, bends=[CODO, CODO_2, CODO]))


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


async def test_s4_without_samples_there_are_eighteen_holes_without_tees():
    """
    GIVEN: Un campo sin muestras
    WHEN: Se leen
    THEN: 18 hoyos, del 1 al 18, sin ninguna barra (todas recogen, sin muestra)
    """
    uow, course = await _setup()

    holes = await _read(uow, course)

    assert [h.hole_number for h in holes] == list(range(1, 19))
    assert all(h.tees == [] for h in holes)


async def test_s4_first_sample_is_the_oldest():
    """
    GIVEN: Tres muestras del hoyo 5 de la misma barra que llegan una detrás de otra
           (codo A, codo B, sin codo)
    WHEN: Se leen
    THEN: La primera de esa barra es la del codo A
    """
    uow, course = await _setup()
    await _submit(uow, course, hole=5, bends=[CODO])
    await _submit(uow, course, hole=5, bends=[CODO_2])
    await _submit(uow, course, hole=5)

    assert (await _tee_of(uow, course, 5)).first_sample.bends == [_p(CODO)]


async def test_s4_collecting_until_three():
    """
    GIVEN: En el hoyo 1, las amarillas de hombre con dos muestras y las rojas de mujer con tres
    WHEN: Se leen
    THEN: Las amarillas siguen recogiendo; las rojas, no
    """
    uow, course = await _setup()
    for _ in range(2):
        await _submit(uow, course)
    for _ in range(3):
        await _submit(uow, course, tee_color=TeeColor.RED, tee_gender=Gender.FEMALE)

    amarillas = await _tee_of(uow, course)
    rojas = await _tee_of(uow, course, color=TeeColor.RED, gender=Gender.FEMALE)

    assert (amarillas.collecting, rojas.collecting) == (True, False)


async def test_s4_tees_are_ordered_by_their_first_sample():
    """
    GIVEN: En el hoyo 1 llegan, por este orden: rojas de mujer, amarillas de hombre,
           otra de rojas y una de blancas sin género
    WHEN: Se leen
    THEN: Tres barras, en el orden en que llegó su primera muestra
    """
    uow, course = await _setup()
    await _submit(uow, course, tee_color=TeeColor.RED, tee_gender=Gender.FEMALE)
    await _submit(uow, course)
    await _submit(uow, course, tee_color=TeeColor.RED, tee_gender=Gender.FEMALE)
    await _submit(uow, course, tee_color=TeeColor.WHITE, tee_gender=None)

    tees = (await _hole(uow, course)).tees

    assert [(t.tee_color, t.tee_gender) for t in tees] == [
        ("RED", "FEMALE"),
        ("YELLOW", "MALE"),
        ("WHITE", None),
    ]


async def test_s4_only_that_course():
    """
    GIVEN: Una muestra del hoyo 1 en otro campo
    WHEN: Se leen las de este
    THEN: Su hoyo 1 no tiene barras
    """
    uow, course = await _setup()
    otro = _course()
    await uow.golf_courses.save(otro)
    await _submit(uow, otro)

    assert (await _hole(uow, course)).tees == []


async def test_s4_the_read_does_not_say_how_many_or_who():
    """
    GIVEN: Un hoyo con dos muestras de una barra
    WHEN: Se lee
    THEN: Solo trae el número de hoyo y, por barra, color, género, la primera
          muestra (salida, codos, green) y si recoge
    """
    uow, course = await _setup()
    await _submit(uow, course)
    await _submit(uow, course)

    hole = (await _hole(uow, course)).model_dump()

    assert set(hole) == {"hole_number", "tees"}
    (tee,) = hole["tees"]
    assert set(tee) == {"tee_color", "tee_gender", "first_sample", "collecting"}
    assert set(tee["first_sample"]) == {"tee", "bends", "green_center"}


# ============================================================================
# S5 — El id lo pone el móvil: una repetida cuenta una vez
# ============================================================================


async def test_s5_the_same_id_twice_counts_once():
    """
    GIVEN: Una muestra guardada (el móvil no recibió la respuesta y la reenvía)
    WHEN: Llega otra vez con el mismo id, aunque sea de otro jugador o pasados 10 minutos
    THEN: Sin error, y sigue habiendo una
    """
    uow, course = await _setup()
    sample_id = uuid4()
    await _submit(uow, course, sample_id=sample_id, user=JUGADOR)
    uow.reloj.advance(600)

    await _submit(uow, course, sample_id=sample_id, user=JUGADOR)
    await _submit(uow, course, sample_id=sample_id, user=OTRO)

    assert await _stored(uow, course) == 1


async def test_s5_the_same_id_in_another_hole_is_not_stored():
    """
    GIVEN: Una muestra guardada en el hoyo 1
    WHEN: Llega su id en una muestra del hoyo 2
    THEN: No se guarda: el id es único en toda la tabla
    """
    uow, course = await _setup()
    sample_id = uuid4()
    await _submit(uow, course, sample_id=sample_id)

    await _submit(uow, course, hole=2, sample_id=sample_id)

    assert await _stored(uow, course, 2) == 0


async def test_s5_a_repeated_id_does_not_use_a_slot():
    """
    GIVEN: Una muestra guardada, y su id repetido dos veces más
    WHEN: Llegan dos muestras nuevas
    THEN: Se guardan las dos: el hoyo se llena con tres muestras distintas
    """
    uow, course = await _setup()
    sample_id = uuid4()
    for _ in range(3):
        await _submit(uow, course, sample_id=sample_id)

    await _submit(uow, course)
    await _submit(uow, course)

    assert await _stored(uow, course) == 3
    assert (await _tee_of(uow, course)).collecting is False


# ============================================================================
# S6 — Una por jugador, campo y hoyo cada 10 minutos
# ============================================================================


async def test_s6_the_same_player_before_ten_minutes_is_dropped():
    """
    GIVEN: Una muestra guardada del jugador en el hoyo 1
    WHEN: Manda otra a los 599 segundos
    THEN: Sin error, y no se guarda
    """
    uow, course = await _setup()
    await _submit(uow, course, user=JUGADOR)
    uow.reloj.advance(599)

    await _submit(uow, course, user=JUGADOR)

    assert await _stored(uow, course) == 1


async def test_s6_the_same_player_after_ten_minutes_is_stored():
    """
    GIVEN: Una muestra guardada del jugador en el hoyo 1
    WHEN: Manda otra a los 600 segundos
    THEN: Se guarda
    """
    uow, course = await _setup()
    await _submit(uow, course, user=JUGADOR)
    uow.reloj.advance(600)

    await _submit(uow, course, user=JUGADOR)

    assert await _stored(uow, course) == 2


async def test_s6_other_players_holes_and_courses_are_not_affected():
    """
    GIVEN: Una muestra guardada del jugador en el hoyo 1
    WHEN: En seguida, otro jugador manda el hoyo 1, y él manda el hoyo 2 y el 1 de otro campo
    THEN: Se guardan las tres
    """
    uow, course = await _setup()
    otro_campo = _course()
    await uow.golf_courses.save(otro_campo)
    await _submit(uow, course, user=JUGADOR)

    await _submit(uow, course, user=OTRO)
    await _submit(uow, course, hole=2, user=JUGADOR)
    await _submit(uow, otro_campo, user=JUGADOR)

    assert await _stored(uow, course, 1) == 2
    assert await _stored(uow, course, 2) == 1
    assert await _stored(uow, otro_campo, 1) == 1


@pytest.mark.parametrize("cause", ["invalid", "duplicate", "full"])
async def test_s6_a_sample_not_stored_does_not_open_the_window(cause):
    """
    GIVEN: Una muestra del jugador que no se guarda: imposible (tres codos), con
           un id ya guardado, o con el hoyo ya lleno
    WHEN: Se mira su ventana del hoyo 1
    THEN: Sigue abierta: solo la gasta una muestra que de verdad se guardó
    """
    uow, course = await _setup()
    if cause == "invalid":
        await _submit(uow, course, user=JUGADOR, bends=[CODO, CODO_2, CODO])
    elif cause == "duplicate":
        sample_id = uuid4()
        await _submit(uow, course, sample_id=sample_id)
        await _submit(uow, course, sample_id=sample_id, user=JUGADOR)
    else:
        for _ in range(3):
            await _submit(uow, course)
        await _submit(uow, course, user=JUGADOR)

    assert _window_open(uow, course)


async def test_s6_after_an_invalid_one_the_next_is_stored():
    """
    GIVEN: Una muestra imposible del jugador (green a 30 m)
    WHEN: Manda en seguida una buena
    THEN: Se guarda la buena
    """
    uow, course = await _setup()
    await _submit(uow, course, user=JUGADOR, green=_north(30))

    await _submit(uow, course, user=JUGADOR)

    assert await _stored(uow, course) == 1


async def test_s6_a_failed_transaction_does_not_open_the_window():
    """
    GIVEN: Una transacción que falla al confirmar
    WHEN: El jugador manda una muestra (falla) y la reintenta en seguida
    THEN: El primer intento da error y no gasta su ventana; el reintento se guarda
    """
    uow, course = await _setup(uow=UoWQueFallaAlConfirmar())
    uow.failures = 1

    with pytest.raises(RuntimeError):
        await _use_case(uow).execute(_request(course, user=JUGADOR))
    assert _window_open(uow, course)

    await _submit(uow, course, user=JUGADOR)
    assert not _window_open(uow, course)


# ============================================================================
# S7 — Lo que queda en el log
# ============================================================================


@pytest.mark.parametrize("cause", ["far", "full", "sender", "duplicate"])
async def test_s7_the_drop_log_has_no_coordinates_and_no_player(cause, caplog):
    """
    GIVEN: Una muestra que se descarta: lejos del campo, con el hoyo lleno, por la
           ventana del jugador o con un id repetido
    WHEN: Se descarta
    THEN: El log no lleva latitud, longitud ni el id del jugador
    """
    uow, course = await _setup(location=CourseLocation(latitude=36.33, longitude=-5.33))
    if cause != "far":
        uow, course = await _setup()
    sample_id = uuid4()
    if cause == "full":
        for _ in range(3):
            await _submit(uow, course)
    elif cause == "sender":
        await _submit(uow, course, user=JUGADOR)
    elif cause == "duplicate":
        await _submit(uow, course, sample_id=sample_id)
    caplog.clear()

    with caplog.at_level(logging.DEBUG):
        await _submit(uow, course, user=JUGADOR, sample_id=sample_id, bends=[CODO])

    text = "\n".join(record.getMessage() for record in caplog.records)
    assert text  # Algo se registró: si no, el test no prueba nada
    for secret in (JUGADOR, "36.28", "-5.33", "36.2815", "-5.331", str(GREEN[0])[:6]):
        assert secret not in text


# ============================================================================
# S8 — Por barra: cada una sale de un sitio
# ============================================================================


async def test_s8_the_cap_is_per_tee():
    """
    GIVEN: Tres muestras del hoyo 1 desde amarillas de hombre y tres desde rojas de mujer
    WHEN: Llega una cuarta desde amarillas de hombre
    THEN: Las seis primeras se guardan; la cuarta amarilla, no
    """
    uow, course = await _setup()
    for _ in range(3):
        await _submit(uow, course)
        await _submit(uow, course, tee_color=TeeColor.RED, tee_gender=Gender.FEMALE)

    await _submit(uow, course)

    assert await _stored(uow, course) == 3
    assert await _stored(uow, course, color=TeeColor.RED, gender=Gender.FEMALE) == 3


async def test_s8_a_genderless_tee_is_its_own_tee():
    """
    GIVEN: Tres muestras desde amarillas de hombre (esa barra ya no recoge)
    WHEN: Llega una desde las blancas, sin género
    THEN: Se guarda, y las blancas siguen recogiendo
    """
    uow, course = await _setup()
    for _ in range(3):
        await _submit(uow, course)

    await _submit(uow, course, tee_color=TeeColor.WHITE, tee_gender=None)

    blancas = {"color": TeeColor.WHITE, "gender": None}
    assert await _stored(uow, course, **blancas) == 1
    assert (await _tee_of(uow, course, **blancas)).collecting is True


async def test_s8_the_players_window_is_per_tee():
    """
    GIVEN: Una muestra del jugador en el hoyo 1 desde amarillas de hombre
    WHEN: En seguida manda otra del hoyo 1 desde rojas de mujer (cambió de barra)
    THEN: Se guarda
    """
    uow, course = await _setup()
    await _submit(uow, course, user=JUGADOR)

    await _submit(uow, course, user=JUGADOR, tee_color=TeeColor.RED, tee_gender=Gender.FEMALE)

    assert await _stored(uow, course, color=TeeColor.RED, gender=Gender.FEMALE) == 1


# ============================================================================
# S9 — La barra se resuelve contra el campo, como al anotar
# ============================================================================

AMARILLAS_SIN_GENERO = ((TeeColor.YELLOW, None), (TeeColor.RED, Gender.FEMALE))


async def test_s9_on_a_genderless_tee_both_genders_go_to_the_same_tee():
    """
    GIVEN: Un campo con amarillas sin género (las de hombre no existen aparte)
    WHEN: Llegan dos muestras desde amarillas de hombre y dos desde amarillas sin género
    THEN: Son la misma barra: se guardan tres, y la lectura trae una sola, sin género, llena
    """
    uow, course = await _setup(tees=AMARILLAS_SIN_GENERO)

    for gender in (Gender.MALE, None, Gender.MALE, None):
        await _submit(uow, course, tee_gender=gender)

    assert await _stored(uow, course, gender=None) == 3
    assert await _stored(uow, course, gender=Gender.MALE) == 0
    (tee,) = (await _hole(uow, course)).tees
    assert (tee.tee_color, tee.tee_gender, tee.collecting) == ("YELLOW", None, False)


@pytest.mark.parametrize(
    ("color", "gender"),
    [
        (TeeColor.BLUE, Gender.MALE),
        (TeeColor.OTHER, None),
        (TeeColor.YELLOW, Gender.FEMALE),
        (TeeColor.YELLOW, None),
    ],
    ids=["blue-missing", "other-missing", "yellow-female", "yellow-genderless"],
)
async def test_s9_a_tee_the_course_does_not_have_is_dropped(color, gender):
    """
    GIVEN: El campo de prueba (amarillas de hombre, rojas de mujer, blancas sin género)
    WHEN: Llega una muestra desde una barra que no tiene: azules, OTHER, o amarillas de
          mujer o sin género (las amarillas son de hombre: no hay reserva hacia otro género)
    THEN: Sin error, no se guarda nada y no gasta la ventana del jugador
    """
    uow, course = await _setup()

    await _submit(uow, course, user=JUGADOR, tee_color=color, tee_gender=gender)

    assert (await _hole(uow, course)).tees == []
    assert _window_open(uow, course, color, gender)


async def test_s9_the_window_uses_the_resolved_tee():
    """
    GIVEN: Un campo con amarillas sin género, y una muestra del jugador desde amarillas de hombre
    WHEN: En seguida manda otra desde amarillas sin género
    THEN: No se guarda: para el campo es la misma barra
    """
    uow, course = await _setup(tees=AMARILLAS_SIN_GENERO)
    await _submit(uow, course, user=JUGADOR, tee_gender=Gender.MALE)

    await _submit(uow, course, user=JUGADOR, tee_gender=None)

    assert await _stored(uow, course, gender=None) == 1


async def test_s9_a_gendered_request_on_a_genderless_tee_is_stored_under_it():
    """
    GIVEN: El campo de prueba, con blancas sin género
    WHEN: Llega una muestra desde blancas de hombre
    THEN: Se guarda en las blancas sin género (la misma reserva que al anotar)
    """
    uow, course = await _setup()

    await _submit(uow, course, tee_color=TeeColor.WHITE, tee_gender=Gender.MALE)

    assert await _stored(uow, course, color=TeeColor.WHITE, gender=None) == 1
