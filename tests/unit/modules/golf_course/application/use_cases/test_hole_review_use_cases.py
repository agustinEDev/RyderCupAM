"""
Lo que lee el admin para revisar los hoyos (BE #575, 17 oct 2026).

| Caso | Qué                                              | Resultado                                         |
|------|--------------------------------------------------|---------------------------------------------------|
| A1   | la lista                                         | los campos con muestras o líneas, con su nombre; por hoyo, cuántas muestras y si está guardado |
| A1   | un campo sin nada                                | no sale                                            |
| A2   | un campo                                         | sus 18 hoyos: la línea guardada, TODAS sus muestras (id, barra, puntos, día) y los metros de cada barra |
| A2   | una muestra solo green                           | sale con `tee: null`                              |
| A2   | un campo que no existe, o que no ven los jugadores | GolfCourseNotFoundError                          |
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


def _course(name="Valderrama"):
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


async def test_a1_the_list_has_the_courses_with_samples_or_lines():
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
    assert [(h.hole_number, h.samples, h.saved) for h in course.holes] == [
        (1, 2, False),
        (5, 1, False),
        (7, 0, True),
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


async def test_a1_a_hole_with_samples_and_a_saved_line():
    uow, con, _ = await _setup()
    await uow.hole_samples.add(_sample(con))
    await uow.saved_holes.save(
        SavedHole.create(
            golf_course_id=con.id,
            hole_number=1,
            tee=SALIDA,
            bends=(),
            green_center=GREEN,
            saved_by=UserId.generate(),
            course_location=None,
        )
    )

    (course,) = (await ListHoleReviewsUseCase(uow).execute(ListHoleReviewsRequestDTO())).courses

    assert [(h.hole_number, h.samples, h.saved) for h in course.holes] == [(1, 1, True)]


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
