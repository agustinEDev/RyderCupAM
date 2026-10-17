"""
Lo que lee el admin para revisar los hoyos (BE #575, 17 oct 2026).

| Caso | Qué                                              | Resultado                                         |
|------|--------------------------------------------------|---------------------------------------------------|
| A1   | la lista                                         | los campos con hoyos PENDIENTES (con muestras y sin línea guardada), con su nombre; por hoyo, cuántas muestras |
| A1   | un campo sin nada                                | no sale                                            |
| P1   | un hoyo con muestras y sin línea guardada        | sale                                               |
| P2   | un hoyo guardado, tenga las muestras que tenga   | no sale (Agustín, 17 oct: al guardarlo desaparece) |
| P3   | un campo con todos sus hoyos guardados           | no sale                                            |
| P4   | un hoyo reabierto que conserva muestras          | vuelve a salir                                     |
| P5   | un hoyo reabierto sin muestras                   | no sale: no hay nada que revisar                   |
| P6   | los hoyos                                        | de menor a mayor                                   |
| P7   | `saved`                                          | sigue en la respuesta, siempre `false`             |
| A2   | un campo                                         | sus 18 hoyos: la línea guardada, TODAS sus muestras (id, barra, puntos, día) y los metros de cada barra |
| A2   | una muestra solo green                           | sale con `tee: null`                              |
| A2   | un campo que no existe, o que no ven los jugadores | GolfCourseNotFoundError                          |
| A3   | la ubicación del campo                           | viene, para que el admin marque un hoyo sin nada (17 oct); sin ella, null |
| A1   | por nombre                                       | sin mayúsculas ni acentos                          |
"""

from datetime import date
from uuid import uuid4

import pytest

from src.modules.golf_course.application.dtos.hole_review_dtos import (
    GetHoleReviewRequestDTO,
    ListHoleReviewsRequestDTO,
)
from src.modules.golf_course.application.exceptions import GolfCourseNotFoundError
from src.modules.golf_course.application.use_cases.hole_review_use_cases import (
    GetHoleReviewUseCase,
    ListHoleReviewsUseCase,
)
from src.modules.golf_course.domain.entities.golf_course import GolfCourse
from src.modules.golf_course.domain.entities.hole import Hole
from src.modules.golf_course.domain.entities.hole_sample import HoleSample
from src.modules.golf_course.domain.entities.saved_hole import SavedHole
from src.modules.golf_course.domain.entities.tee import Tee
from src.modules.golf_course.domain.value_objects.course_location import CourseLocation
from src.modules.golf_course.domain.value_objects.course_type import CourseType
from src.modules.golf_course.domain.value_objects.geo_point import GeoPoint
from src.modules.golf_course.domain.value_objects.tee_color import TeeColor
from src.modules.golf_course.infrastructure.persistence.in_memory.in_memory_golf_course_unit_of_work import (
    InMemoryGolfCourseUnitOfWork,
)
from src.modules.user.domain.value_objects.user_id import UserId
from src.shared.domain.value_objects.country_code import CountryCode
from src.shared.domain.value_objects.gender import Gender

pytestmark = pytest.mark.asyncio

SALIDA = GeoPoint(latitude=36.28, longitude=-5.33)
CODO = GeoPoint(latitude=36.2815, longitude=-5.331)
GREEN = GeoPoint(latitude=36.2827, longitude=-5.33)


def _course(name="Valderrama", location=None):
    amarillas = [Hole(number=i + 1, par=4, stroke_index=i + 1, meters=350 + i) for i in range(18)]
    rojas = [Hole(number=i + 1, par=4, stroke_index=i + 1, meters=300 + i) for i in range(18)]
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
                holes=amarillas,
            ),
            Tee(
                color=TeeColor.RED,
                gender=Gender.FEMALE,
                identifier=None,
                course_rating=70.2,
                slope_rating=120,
                holes=rojas,
            ),
        ],
        holes=amarillas,
        location=location,
    )
    course.approve()
    return course


def _sample(course, hole=1, tee=SALIDA, bends=(CODO,), color=TeeColor.YELLOW, gender=Gender.MALE):
    return HoleSample.reconstruct(
        id=uuid4(),
        golf_course_id=course.id,
        hole_number=hole,
        tee_color=color,
        tee_gender=gender,
        tee=tee,
        bends=bends if tee else (),
        green_center=GREEN,
        received_on=date(2026, 10, 17),
    )


async def _setup():
    uow = InMemoryGolfCourseUnitOfWork()
    con, sin = _course(), _course("Sin nada")
    for c in (con, sin):
        await uow.golf_courses.save(c)
    return uow, con, sin


def _saved(course, hole):
    return SavedHole.create(
        golf_course_id=course.id,
        hole_number=hole,
        tee=SALIDA,
        bends=(),
        green_center=GREEN,
        saved_by=UserId.generate(),
        course_location=None,
    )


async def test_a1_the_list_has_the_courses_with_pending_holes():
    uow, con, _ = await _setup()
    for sample in (
        _sample(con),
        _sample(con, color=TeeColor.RED, gender=Gender.FEMALE),
        _sample(con, hole=5),
    ):
        await uow.hole_samples.add(sample)
    await uow.saved_holes.save(
        SavedHole.create(
            golf_course_id=con.id,
            hole_number=7,
            tee=SALIDA,
            bends=(),
            green_center=GREEN,
            saved_by=UserId.generate(),
            course_location=None,
        )
    )

    (course,) = (await ListHoleReviewsUseCase(uow).execute(ListHoleReviewsRequestDTO())).courses

    assert (course.golf_course_id, course.name) == (str(con.id), "Valderrama")
    # P1/P2: el 7 está guardado y sin muestras: no sale
    assert [(h.hole_number, h.samples, h.model_dump()["saved"]) for h in course.holes] == [
        (1, 2, False),
        (5, 1, False),
    ]


async def test_a1_nothing_to_review_is_an_empty_list():
    uow, _, _ = await _setup()

    assert (await ListHoleReviewsUseCase(uow).execute(ListHoleReviewsRequestDTO())).courses == []


async def test_a2_a_course_with_every_sample_its_line_and_the_metres_of_each_tee():
    uow, con, _ = await _setup()
    primera, solo_green = (
        _sample(con),
        _sample(con, tee=None, color=TeeColor.RED, gender=Gender.FEMALE),
    )
    for sample in (primera, solo_green):
        await uow.hole_samples.add(sample)

    review = await GetHoleReviewUseCase(uow).execute(
        GetHoleReviewRequestDTO(golf_course_id=str(con.id))
    )

    assert review.name == "Valderrama"
    assert [h.hole_number for h in review.holes] == list(range(1, 19))
    uno = review.holes[0]
    assert uno.saved_line is None
    assert [s.id for s in uno.samples] == [primera.id, solo_green.id]
    assert (uno.samples[0].tee_color, uno.samples[0].tee_gender, uno.samples[0].received_on) == (
        "YELLOW",
        "MALE",
        date(2026, 10, 17),
    )
    assert uno.samples[0].tee.latitude == SALIDA.latitude
    assert uno.samples[0].bends[0].latitude == CODO.latitude
    assert uno.samples[1].tee is None
    assert [(t.tee_color, t.tee_gender, t.meters, t.par) for t in uno.tees] == [
        ("YELLOW", "MALE", 350, 4),
        ("RED", "FEMALE", 300, 4),
    ]
    assert review.holes[1].tees[0].meters == 351
    assert review.holes[1].samples == []


async def test_get_review_with_coordinates_returns_the_course_location():
    """
    GIVEN: un campo con coordenadas (A3)
    WHEN: el admin pide su revisión
    THEN: viene su ubicación, para marcar un hoyo sin nada
    """
    uow = InMemoryGolfCourseUnitOfWork()
    con = _course(location=CourseLocation(latitude=36.28, longitude=-5.33))
    await uow.golf_courses.save(con)

    review = await GetHoleReviewUseCase(uow).execute(
        GetHoleReviewRequestDTO(golf_course_id=str(con.id))
    )

    assert (review.location.latitude, review.location.longitude) == (36.28, -5.33)


async def test_get_review_without_coordinates_returns_a_null_location():
    """
    GIVEN: un campo sin coordenadas (A3)
    WHEN: el admin pide su revisión
    THEN: la ubicación viene null
    """
    uow = InMemoryGolfCourseUnitOfWork()
    sin = _course("Sin ubicación")
    await uow.golf_courses.save(sin)

    review = await GetHoleReviewUseCase(uow).execute(
        GetHoleReviewRequestDTO(golf_course_id=str(sin.id))
    )

    assert review.location is None


async def test_a2_the_saved_line_comes_too():
    uow, con, _ = await _setup()
    await uow.saved_holes.save(
        SavedHole.create(
            golf_course_id=con.id,
            hole_number=1,
            tee=SALIDA,
            bends=(CODO,),
            green_center=GREEN,
            saved_by=UserId.generate(),
            course_location=None,
        )
    )

    review = await GetHoleReviewUseCase(uow).execute(
        GetHoleReviewRequestDTO(golf_course_id=str(con.id))
    )

    assert review.holes[0].saved_line.bends[0].latitude == CODO.latitude


async def test_a2_unknown_course():
    uow, _, _ = await _setup()

    with pytest.raises(GolfCourseNotFoundError):
        await GetHoleReviewUseCase(uow).execute(
            GetHoleReviewRequestDTO(golf_course_id=str(uuid4()))
        )


async def test_a1_the_list_is_by_name():
    uow = InMemoryGolfCourseUnitOfWork()
    zahara, alcanada = _course("Zahara"), _course("Alcanada")
    for c in (zahara, alcanada):
        await uow.golf_courses.save(c)
        await uow.hole_samples.add(_sample(c))

    courses = (await ListHoleReviewsUseCase(uow).execute(ListHoleReviewsRequestDTO())).courses

    assert [c.name for c in courses] == ["Alcanada", "Zahara"]


async def test_a1_by_name_without_case_or_accents():
    """Á y a, Z y z: el orden de un listado en castellano (revisión, 17 oct)."""
    uow = InMemoryGolfCourseUnitOfWork()
    for name in ("Zahara", "el Saler", "Ávila Golf"):
        c = _course(name)
        await uow.golf_courses.save(c)
        await uow.hole_samples.add(_sample(c))

    courses = (await ListHoleReviewsUseCase(uow).execute(ListHoleReviewsRequestDTO())).courses

    assert [c.name for c in courses] == ["Ávila Golf", "el Saler", "Zahara"]


async def test_p2_a_saved_hole_with_samples_is_not_pending():
    uow, con, _ = await _setup()
    await uow.hole_samples.add(_sample(con))
    await uow.hole_samples.add(_sample(con, hole=2))
    await uow.saved_holes.save(_saved(con, 1))

    (course,) = (await ListHoleReviewsUseCase(uow).execute(ListHoleReviewsRequestDTO())).courses

    assert [(h.hole_number, h.samples, h.model_dump()["saved"]) for h in course.holes] == [
        (2, 1, False)
    ]


async def test_p3_a_course_with_every_hole_saved_is_not_listed():
    uow, con, _ = await _setup()
    for hole in (1, 2):
        await uow.hole_samples.add(_sample(con, hole=hole))
        await uow.saved_holes.save(_saved(con, hole))

    assert (await ListHoleReviewsUseCase(uow).execute(ListHoleReviewsRequestDTO())).courses == []


async def test_p4_a_reopened_hole_with_samples_is_pending_again():
    uow, con, _ = await _setup()
    await uow.hole_samples.add(_sample(con))
    await uow.saved_holes.save(_saved(con, 1))
    await uow.saved_holes.delete(con.id, 1)

    (course,) = (await ListHoleReviewsUseCase(uow).execute(ListHoleReviewsRequestDTO())).courses

    assert [(h.hole_number, h.samples) for h in course.holes] == [(1, 1)]


async def test_p5_a_reopened_hole_without_samples_is_not_listed():
    """El 3 se reabre sin muestras: no vuelve; el 4, con una, sí."""
    uow, con, _ = await _setup()
    await uow.hole_samples.add(_sample(con, hole=4))
    for hole in (3, 4):
        await uow.saved_holes.save(_saved(con, hole))
        await uow.saved_holes.delete(con.id, hole)

    (course,) = (await ListHoleReviewsUseCase(uow).execute(ListHoleReviewsRequestDTO())).courses

    assert [h.hole_number for h in course.holes] == [4]


async def test_p6_the_holes_go_from_lowest_to_highest():
    uow, con, _ = await _setup()
    for hole in (12, 3, 9):
        await uow.hole_samples.add(_sample(con, hole=hole))

    (course,) = (await ListHoleReviewsUseCase(uow).execute(ListHoleReviewsRequestDTO())).courses

    assert [h.hole_number for h in course.holes] == [3, 9, 12]


async def test_a2_a_course_players_cannot_see_is_not_found():
    uow = InMemoryGolfCourseUnitOfWork()
    pendiente = GolfCourse.create(
        name="Pendiente",
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
    )
    await uow.golf_courses.save(pendiente)

    with pytest.raises(GolfCourseNotFoundError):
        await GetHoleReviewUseCase(uow).execute(
            GetHoleReviewRequestDTO(golf_course_id=str(pendiente.id))
        )
