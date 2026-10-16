"""
Casos de uso de la línea que el admin guarda de cada hoyo (BE #575, 17 oct 2026).

| Caso | Qué                                                | Resultado                                     |
|------|----------------------------------------------------|-----------------------------------------------|
| A3   | guardar la línea de un hoyo                        | se guarda, con el admin; se devuelve          |
| A3   | guardar encima                                     | la nueva sustituye a la de antes              |
| A3   | una línea imposible (3 codos, green a 800 m)       | InvalidHoleLineError                          |
| A3   | campo que no existe / hoyo 0 o 19                  | GolfCourseNotFoundError / HoleNotInCourseError |
| A4   | borrar una muestra del campo                       | se va, y deja hueco                           |
| A4   | una muestra de otro campo, o que no existe         | HoleSampleNotFoundError                       |
| A5   | reabrir el hoyo                                    | se quita la línea; sin línea, nada            |
| V4   | un hoyo guardado                                   | no recoge: una muestra nueva no se guarda     |
| V1   | la lectura de un hoyo guardado                     | trae su línea y no recoge                     |
"""

from uuid import uuid4

import pytest

from src.modules.golf_course.application.dtos.hole_sample_dtos import (
    ListHoleSamplesRequestDTO,
    PointDTO,
    SubmitHoleSampleRequestDTO,
)
from src.modules.golf_course.application.dtos.saved_hole_dtos import (
    DeleteHoleSampleRequestDTO,
    ReopenHoleRequestDTO,
    SaveHoleLineRequestDTO,
)
from src.modules.golf_course.application.exceptions import (
    GolfCourseNotFoundError,
    HoleNotInCourseError,
    HoleSampleNotFoundError,
    InvalidHoleLineError,
)
from src.modules.golf_course.application.use_cases.hole_sample_use_cases import (
    ListHoleSamplesUseCase,
    SubmitHoleSampleUseCase,
)
from src.modules.golf_course.application.use_cases.saved_hole_use_cases import (
    DeleteHoleSampleUseCase,
    ReopenHoleUseCase,
    SaveHoleLineUseCase,
)
from src.modules.golf_course.domain.entities.golf_course import GolfCourse
from src.modules.golf_course.domain.entities.hole import Hole
from src.modules.golf_course.domain.entities.tee import Tee
from src.modules.golf_course.domain.value_objects.course_type import CourseType
from src.modules.golf_course.domain.value_objects.geo_point import GeoPoint
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

M_PER_DEGREE = 6_371_000.0 * 3.141592653589793 / 180
SALIDA = (36.28, -5.33)
ADMIN = str(UserId.generate().value)


def _north(metres: float) -> tuple[float, float]:
    return (SALIDA[0] + metres / M_PER_DEGREE, SALIDA[1])


def _p(point) -> PointDTO:
    return PointDTO(latitude=point[0], longitude=point[1])


async def _setup():
    uow = InMemoryGolfCourseUnitOfWork()
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
    )
    course.approve()
    await uow.golf_courses.save(course)
    return uow, course


def _save_request(course, hole=1, bends=(_north(150),), green=_north(300)):
    return SaveHoleLineRequestDTO(
        golf_course_id=str(course.id),
        hole_number=hole,
        admin_id=ADMIN,
        tee=_p(SALIDA),
        bends=[_p(b) for b in bends],
        green_center=_p(green),
    )


async def _submit(uow, course, hole=1):
    await SubmitHoleSampleUseCase(uow, InMemoryRecentHoleSampleSenders()).execute(
        SubmitHoleSampleRequestDTO(
            id=uuid4(),
            golf_course_id=str(course.id),
            hole_number=hole,
            user_id=str(uuid4()),
            tee_color=TeeColor.YELLOW,
            tee_gender=Gender.MALE,
            tee=_p(SALIDA),
            green_center=_p(_north(300)),
        )
    )


async def test_a3_saving_the_line_of_a_hole():
    uow, course = await _setup()

    saved = await SaveHoleLineUseCase(uow).execute(_save_request(course))

    stored = await uow.saved_holes.get(course.id, 1)
    assert stored.play_line == (GeoPoint(*SALIDA), GeoPoint(*_north(150)), GeoPoint(*_north(300)))
    assert str(stored.saved_by.value) == ADMIN
    assert saved.bends == [_p(_north(150))]


async def test_a3_saving_again_replaces_it():
    uow, course = await _setup()
    use_case = SaveHoleLineUseCase(uow)
    await use_case.execute(_save_request(course))

    await use_case.execute(_save_request(course, bends=(), green=_north(320)))

    stored = await uow.saved_holes.get(course.id, 1)
    assert (stored.bends, stored.green_center) == ((), GeoPoint(*_north(320)))


@pytest.mark.parametrize(
    "changes",
    [
        pytest.param({"bends": (_north(50), _north(100), _north(150))}, id="tres codos"),
        pytest.param({"bends": (), "green": _north(800)}, id="green a 800 m"),
        pytest.param({"bends": (), "green": (91.0, -5.33)}, id="latitud imposible"),
    ],
)
async def test_a3_an_impossible_line_is_rejected(changes):
    uow, course = await _setup()

    with pytest.raises(InvalidHoleLineError):
        await SaveHoleLineUseCase(uow).execute(_save_request(course, **changes))

    assert await uow.saved_holes.get(course.id, 1) is None


async def test_a3_unknown_course_and_hole_outside_a_round():
    uow, course = await _setup()

    with pytest.raises(GolfCourseNotFoundError):
        await SaveHoleLineUseCase(uow).execute(
            _save_request(course).model_copy(update={"golf_course_id": str(uuid4())})
        )
    for hole in (0, 19):
        with pytest.raises(HoleNotInCourseError):
            await SaveHoleLineUseCase(uow).execute(_save_request(course, hole=hole))


async def test_a4_deleting_a_sample_frees_its_slot():
    uow, course = await _setup()
    for _ in range(3):
        await _submit(uow, course)
    (first, *_rest) = await uow.hole_samples.list_by_course(course.id)

    await DeleteHoleSampleUseCase(uow).execute(
        DeleteHoleSampleRequestDTO(golf_course_id=str(course.id), sample_id=first.id)
    )
    await _submit(uow, course)

    ids = [x.id for x in await uow.hole_samples.list_by_course(course.id)]
    assert first.id not in ids
    assert len(ids) == 3


async def test_a4_a_sample_of_another_course_or_unknown_is_not_found():
    uow, course = await _setup()
    otro = GolfCourse.create(
        name="Otro",
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
    otro.approve()
    await uow.golf_courses.save(otro)
    await _submit(uow, otro)
    (ajena,) = await uow.hole_samples.list_by_course(otro.id)

    for sample_id in (ajena.id, uuid4()):
        with pytest.raises(HoleSampleNotFoundError):
            await DeleteHoleSampleUseCase(uow).execute(
                DeleteHoleSampleRequestDTO(golf_course_id=str(course.id), sample_id=sample_id)
            )
    assert len(await uow.hole_samples.list_by_course(otro.id)) == 1


async def test_a5_reopening_removes_the_line():
    uow, course = await _setup()
    await SaveHoleLineUseCase(uow).execute(_save_request(course))

    await ReopenHoleUseCase(uow).execute(
        ReopenHoleRequestDTO(golf_course_id=str(course.id), hole_number=1)
    )
    # Sin línea, reabrir no hace nada (ni falla)
    await ReopenHoleUseCase(uow).execute(
        ReopenHoleRequestDTO(golf_course_id=str(course.id), hole_number=1)
    )

    assert await uow.saved_holes.get(course.id, 1) is None


async def test_v4_a_saved_hole_does_not_collect():
    uow, course = await _setup()
    await SaveHoleLineUseCase(uow).execute(_save_request(course))

    await _submit(uow, course)
    await _submit(uow, course, hole=2)

    samples = await uow.hole_samples.list_by_course(course.id)
    assert [x.hole_number for x in samples] == [2]


async def test_v1_the_read_brings_the_saved_line_and_it_does_not_collect():
    uow, course = await _setup()
    await SaveHoleLineUseCase(uow).execute(_save_request(course))

    holes = (
        await ListHoleSamplesUseCase(uow).execute(
            ListHoleSamplesRequestDTO(golf_course_id=str(course.id))
        )
    ).holes

    assert holes[0].saved_line.tee == _p(SALIDA)
    assert holes[0].saved_line.bends == [_p(_north(150))]
    assert holes[0].collecting is False
    assert (holes[1].saved_line, holes[1].collecting) == (None, True)


async def test_v1_reopened_it_collects_again():
    uow, course = await _setup()
    await SaveHoleLineUseCase(uow).execute(_save_request(course))
    await ReopenHoleUseCase(uow).execute(
        ReopenHoleRequestDTO(golf_course_id=str(course.id), hole_number=1)
    )

    await _submit(uow, course)

    assert len(await uow.hole_samples.list_by_course(course.id)) == 1
