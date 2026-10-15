"""
Tests de los casos de uso de las marcas de hoyo de los jugadores (BE #532, PR C).

Un hoyo sin datos se marca entero (salida, codos y green); uno con salida en el
mapa aprobado, solo el green; uno con salida y green aprobados ya no se marca.
Un mapa pendiente o rechazado no cuenta: los jugadores no lo ven.
"""

from datetime import UTC, datetime, timedelta

import pytest

from src.modules.golf_course.application.dtos.hole_mark_dtos import (
    ListMyHoleMarksRequestDTO,
    PointDTO,
    SaveHoleMarkRequestDTO,
)
from src.modules.golf_course.application.exceptions import (
    GolfCourseNotFoundError,
    HoleAlreadyMappedError,
    HoleNotInCourseError,
    TeeRequiredError,
)
from src.modules.golf_course.application.use_cases.hole_mark_use_cases import (
    ListMyHoleMarksUseCase,
    SaveHoleMarkUseCase,
)
from src.modules.golf_course.domain.entities.course_hole_map import CourseHoleMap
from src.modules.golf_course.domain.entities.golf_course import GolfCourse
from src.modules.golf_course.domain.entities.hole import Hole
from src.modules.golf_course.domain.entities.hole_mark import (
    HoleMarkFarFromCourseError,
    HoleMarkOutOfRangeError,
    InvalidHoleMarkError,
)
from src.modules.golf_course.domain.entities.tee import Tee
from src.modules.golf_course.domain.value_objects.course_location import CourseLocation
from src.modules.golf_course.domain.value_objects.course_type import CourseType
from src.modules.golf_course.domain.value_objects.geo_point import GeoPoint
from src.modules.golf_course.domain.value_objects.golf_course_id import GolfCourseId
from src.modules.golf_course.domain.value_objects.green_position import GreenPosition
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

M_PER_DEGREE = 6_371_000.0 * 3.141592653589793 / 180
SALIDA = (36.28, -5.33)
GREEN = (36.28 + 300 / M_PER_DEGREE, -5.33)  # 300 m al norte de la salida
CODO = (36.2815, -5.331)
JUGADOR = UserId.generate()
OTRO = UserId.generate()


def _p(point: tuple[float, float]) -> PointDTO:
    return PointDTO(latitude=point[0], longitude=point[1])


def _course(physical_holes=None, location=None) -> GolfCourse:
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
    course.approve()
    return course


def _mapped(number: int, with_green: bool) -> MappedHole:
    tee, green = GeoPoint(*SALIDA), GeoPoint(*GREEN)
    return MappedHole(
        number=number,
        play_line=(tee, green),
        line_source=PositionSource.OSM,
        green=GreenPosition(front=green, center=green, back=green, source=PositionSource.OSM)
        if with_green
        else None,
    )


async def _setup(map_status=None, holes=(), **course_args):
    """Un campo y, si se pide, su mapa con esos hoyos (número, ¿con green?)."""
    uow = InMemoryGolfCourseUnitOfWork()
    course = _course(**course_args)
    await uow.golf_courses.save(course)
    if map_status is not None:
        hole_map = CourseHoleMap.create(
            golf_course_id=course.id,
            holes=[_mapped(n, g) for n, g in holes],
            osm_reference="way/1",
            imported_at=datetime(2026, 10, 15, 9, 0),
        )
        if map_status is HoleMapStatus.APPROVED:
            hole_map.approve(reviewer_id=UserId.generate())
        elif map_status is HoleMapStatus.REJECTED:
            hole_map.reject(reviewer_id=UserId.generate())
        await uow.hole_maps.save(hole_map)
    return uow, course


def _request(course, hole=1, user=JUGADOR, tee=SALIDA, bends=(), green=GREEN, marked_at=None):
    return SaveHoleMarkRequestDTO(
        golf_course_id=str(course.id if hasattr(course, "id") else course),
        hole_number=hole,
        user_id=str(user),
        tee=_p(tee) if tee is not None else None,
        bends=[_p(b) for b in bends],
        green_center=_p(green),
        marked_at=marked_at,
    )


async def _mine(uow, course, user=JUGADOR):
    return await ListMyHoleMarksUseCase(uow).execute(
        ListMyHoleMarksRequestDTO(golf_course_id=str(course.id), user_id=str(user))
    )


# ============================================================================
# U1 — Marcar un hoyo sin datos
# ============================================================================


@pytest.mark.asyncio
async def test_u1_full_mark_on_a_course_without_map_is_saved():
    """
    GIVEN: Un campo sin mapa
    WHEN: El jugador marca salida, un codo y green en el hoyo 3
    THEN: Se guarda y se devuelve con sus puntos y la fecha; sale entre las suyas
    """
    uow, course = await _setup()

    dto = await SaveHoleMarkUseCase(uow).execute(_request(course, hole=3, bends=[CODO]))

    assert dto.hole_number == 3
    assert dto.tee == _p(SALIDA)
    assert dto.bends == [_p(CODO)]
    assert dto.green_center == _p(GREEN)
    assert dto.marked_at is not None
    assert await _mine(uow, course) == [dto]


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [HoleMapStatus.PENDING_REVIEW, HoleMapStatus.REJECTED])
async def test_u1_a_map_not_approved_does_not_count(status):
    """
    GIVEN: Un mapa pendiente o rechazado que tiene el hoyo 1 con salida y green
    WHEN: El jugador marca el hoyo 1 entero
    THEN: Se guarda: los jugadores no ven ese mapa, para ellos el hoyo no tiene datos
    """
    uow, course = await _setup(map_status=status, holes=[(1, True)])

    dto = await SaveHoleMarkUseCase(uow).execute(_request(course))

    assert dto.tee == _p(SALIDA)


@pytest.mark.asyncio
async def test_u1_hole_missing_from_an_approved_partial_map_is_marked_whole():
    """
    GIVEN: Un mapa aprobado que no trae el hoyo 4
    WHEN: El jugador marca el hoyo 4 entero
    THEN: Se guarda
    """
    uow, course = await _setup(map_status=HoleMapStatus.APPROVED, holes=[(1, True)])

    dto = await SaveHoleMarkUseCase(uow).execute(_request(course, hole=4))

    assert dto.hole_number == 4


# ============================================================================
# U2 — Una marca por jugador y hoyo
# ============================================================================


@pytest.mark.asyncio
async def test_u2_marking_again_replaces_the_previous_mark():
    """
    GIVEN: El jugador ya marcó el hoyo 1
    WHEN: Lo vuelve a marcar con otro green
    THEN: Queda solo la marca nueva
    """
    uow, course = await _setup()
    use_case = SaveHoleMarkUseCase(uow)
    await use_case.execute(_request(course, bends=[CODO]))
    otro_green = (GREEN[0] + 0.0005, GREEN[1])

    await use_case.execute(_request(course, green=otro_green))

    (mark,) = await _mine(uow, course)
    assert mark.green_center == _p(otro_green)
    assert mark.bends == []


@pytest.mark.asyncio
async def test_u2_each_player_has_their_own_mark():
    """
    GIVEN: Dos jugadores que marcan el mismo hoyo
    WHEN: Cada uno pide las suyas
    THEN: Cada uno ve solo la suya
    """
    uow, course = await _setup()
    use_case = SaveHoleMarkUseCase(uow)
    otro_green = (GREEN[0] + 0.0005, GREEN[1])
    await use_case.execute(_request(course))
    await use_case.execute(_request(course, user=OTRO, green=otro_green))

    (mia,) = await _mine(uow, course)
    (suya,) = await _mine(uow, course, user=OTRO)
    assert mia.green_center == _p(GREEN)
    assert suya.green_center == _p(otro_green)


@pytest.mark.asyncio
async def test_u2_mine_come_ordered_by_hole_and_only_from_that_course():
    """
    GIVEN: Marcas del jugador en los hoyos 5, 2 y 9, y otra en otro campo
    WHEN: Pide las suyas del primer campo
    THEN: Las tres, por orden de hoyo
    """
    uow, course = await _setup()
    otro_campo = _course()
    await uow.golf_courses.save(otro_campo)
    use_case = SaveHoleMarkUseCase(uow)
    for hole in (5, 2, 9):
        await use_case.execute(_request(course, hole=hole))
    await use_case.execute(_request(otro_campo, hole=1))

    assert [m.hole_number for m in await _mine(uow, course)] == [2, 5, 9]


# ============================================================================
# U3 — Hoyo con datos aprobados
# ============================================================================


@pytest.mark.asyncio
async def test_u3_hole_with_tee_and_green_approved_cannot_be_marked():
    """
    GIVEN: Un mapa aprobado con el hoyo 1 completo (salida y green)
    WHEN: El jugador lo marca
    THEN: HoleAlreadyMappedError, y no se guarda nada
    """
    uow, course = await _setup(map_status=HoleMapStatus.APPROVED, holes=[(1, True)])

    with pytest.raises(HoleAlreadyMappedError):
        await SaveHoleMarkUseCase(uow).execute(_request(course))
    with pytest.raises(HoleAlreadyMappedError):
        await SaveHoleMarkUseCase(uow).execute(_request(course, tee=None))
    assert await _mine(uow, course) == []


@pytest.mark.asyncio
async def test_u3_hole_with_tee_only_takes_a_green_only_mark():
    """
    GIVEN: Un mapa aprobado con el hoyo 2 con salida y sin green
    WHEN: El jugador marca solo el green
    THEN: Se guarda sin salida ni codos
    """
    uow, course = await _setup(map_status=HoleMapStatus.APPROVED, holes=[(2, False)])

    dto = await SaveHoleMarkUseCase(uow).execute(_request(course, hole=2, tee=None))

    assert dto.tee is None
    assert dto.bends == []
    assert dto.green_center == _p(GREEN)


@pytest.mark.asyncio
async def test_u3_hole_with_tee_keeps_only_the_green_of_a_full_mark():
    """
    GIVEN: Un hoyo con salida aprobada (se aprobó mientras el jugador marcaba sin cobertura)
    WHEN: Llega su marca con salida, codo y green
    THEN: Se guarda solo su green, sin salida ni codos (Agustín, 15 oct)
    """
    uow, course = await _setup(map_status=HoleMapStatus.APPROVED, holes=[(2, False)])

    dto = await SaveHoleMarkUseCase(uow).execute(_request(course, hole=2, bends=[CODO]))

    assert (dto.tee, dto.bends, dto.green_center) == (None, [], _p(GREEN))
    (guardada,) = await _mine(uow, course)
    assert (guardada.tee, guardada.bends) == (None, [])


@pytest.mark.asyncio
@pytest.mark.parametrize("metres", [20, 900])
async def test_u3_green_only_is_measured_from_the_approved_tee(metres):
    """
    GIVEN: Un hoyo con salida aprobada
    WHEN: Se marca el green a 20 m o a 900 m de esa salida
    THEN: HoleMarkOutOfRangeError
    """
    uow, course = await _setup(map_status=HoleMapStatus.APPROVED, holes=[(2, False)])
    green = (SALIDA[0] + metres / M_PER_DEGREE, SALIDA[1])

    with pytest.raises(HoleMarkOutOfRangeError):
        await SaveHoleMarkUseCase(uow).execute(_request(course, hole=2, tee=None, green=green))


# ============================================================================
# U4 — Sin salida en ningún sitio
# ============================================================================


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [None, HoleMapStatus.PENDING_REVIEW])
async def test_u4_a_hole_without_tee_needs_one_in_the_mark(status):
    """
    GIVEN: Un hoyo sin salida que vean los jugadores (sin mapa, o con uno pendiente)
    WHEN: La marca trae solo el green
    THEN: TeeRequiredError
    """
    uow, course = await _setup(map_status=status, holes=[(1, False)])

    with pytest.raises(TeeRequiredError):
        await SaveHoleMarkUseCase(uow).execute(_request(course, tee=None))


# ============================================================================
# U5 — Campo y hoyo
# ============================================================================


@pytest.mark.asyncio
async def test_u5_unknown_course():
    """
    GIVEN: Un id que no es de ningún campo
    WHEN: Se marca o se piden las marcas
    THEN: GolfCourseNotFoundError
    """
    uow, _ = await _setup()
    nadie = GolfCourseId.generate()

    with pytest.raises(GolfCourseNotFoundError):
        await SaveHoleMarkUseCase(uow).execute(_request(nadie))
    with pytest.raises(GolfCourseNotFoundError):
        await ListMyHoleMarksUseCase(uow).execute(
            ListMyHoleMarksRequestDTO(golf_course_id=str(nadie), user_id=str(JUGADOR))
        )


@pytest.mark.asyncio
@pytest.mark.parametrize(("physical_holes", "hole"), [(9, 0), (18, 19), (None, 19), (None, 0)])
async def test_u5_hole_outside_a_round(physical_holes, hole):
    """
    GIVEN: Un campo de 9, uno de 18 y uno sin el dato
    WHEN: Se marca el 0 o el 19
    THEN: HoleNotInCourseError
    """
    uow, course = await _setup(physical_holes=physical_holes)

    with pytest.raises(HoleNotInCourseError):
        await SaveHoleMarkUseCase(uow).execute(_request(course, hole=hole))


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("physical_holes", "hole"), [(9, 9), (9, 10), (9, 18), (18, 18), (None, 18), (9, 1)]
)
async def test_u5_any_hole_of_the_round_is_fine_even_on_nine_holes(physical_holes, hole):
    """
    GIVEN: Un campo de 9 (se juega dos veces), uno de 18 y uno sin el dato
    WHEN: Se marca cualquier hoyo del 1 al 18 (en el de 9, también del 10 al 18:
          la segunda vuelta suele salir de otras salidas)
    THEN: Se guarda
    """
    uow, course = await _setup(physical_holes=physical_holes)

    dto = await SaveHoleMarkUseCase(uow).execute(_request(course, hole=hole))

    assert dto.hole_number == hole


@pytest.mark.asyncio
async def test_u5_on_nine_holes_the_10th_is_its_own_mark():
    """
    GIVEN: Un campo de 9 hoyos
    WHEN: El jugador marca el 1 y el 10 con salidas distintas
    THEN: Quedan las dos, cada una con su salida
    """
    uow, course = await _setup(physical_holes=9)
    use_case = SaveHoleMarkUseCase(uow)
    otra_salida = (SALIDA[0] - 0.0003, SALIDA[1])
    await use_case.execute(_request(course, hole=1))
    await use_case.execute(_request(course, hole=10, tee=otra_salida))

    assert [(m.hole_number, m.tee) for m in await _mine(uow, course)] == [
        (1, _p(SALIDA)),
        (10, _p(otra_salida)),
    ]


# ============================================================================
# U6 — Datos imposibles
# ============================================================================


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "changes",
    [
        {"tee": (91.0, -5.33)},
        {"green": (36.29, 181.0)},
        {"bends": [(-91.0, 0.0)]},
        {"bends": [CODO, CODO, CODO]},
    ],
)
async def test_u6_invalid_points_are_rejected(changes):
    """
    GIVEN: Una coordenada fuera de rango, o tres codos
    WHEN: Se marca
    THEN: InvalidHoleMarkError, y no se guarda nada
    """
    uow, course = await _setup()

    with pytest.raises(InvalidHoleMarkError):
        await SaveHoleMarkUseCase(uow).execute(_request(course, **changes))
    assert await _mine(uow, course) == []


@pytest.mark.asyncio
async def test_u6_tee_too_close_to_the_green():
    """
    GIVEN: Un hoyo sin datos
    WHEN: El green se marca a 10 m de la salida
    THEN: HoleMarkOutOfRangeError
    """
    uow, course = await _setup()
    green = (SALIDA[0] + 10 / M_PER_DEGREE, SALIDA[1])

    with pytest.raises(HoleMarkOutOfRangeError):
        await SaveHoleMarkUseCase(uow).execute(_request(course, green=green))


@pytest.mark.asyncio
async def test_u6_far_from_the_course_location():
    """
    GIVEN: Un campo con ubicación a ~5 km de la marca
    WHEN: Se marca
    THEN: HoleMarkFarFromCourseError, y no se guarda
    """
    uow, course = await _setup(location=CourseLocation(latitude=36.33, longitude=-5.33))

    with pytest.raises(HoleMarkFarFromCourseError):
        await SaveHoleMarkUseCase(uow).execute(_request(course))
    assert await _mine(uow, course) == []


@pytest.mark.asyncio
async def test_u6_near_the_course_location_is_fine():
    """
    GIVEN: Un campo con ubicación a ~1 km de la marca
    WHEN: Se marca
    THEN: Se guarda
    """
    uow, course = await _setup(location=CourseLocation(latitude=36.29, longitude=-5.33))

    dto = await SaveHoleMarkUseCase(uow).execute(_request(course))

    assert dto.hole_number == 1


@pytest.mark.asyncio
async def test_u6_green_only_far_from_the_course_location():
    """
    GIVEN: Un hoyo con salida aprobada en un campo con ubicación
    WHEN: El green marcado está a más de 3 km del campo (pero cerca de la salida)
    THEN: HoleMarkFarFromCourseError
    """
    uow, course = await _setup(
        map_status=HoleMapStatus.APPROVED,
        holes=[(2, False)],
        location=CourseLocation(latitude=36.28 - 2.9 / 111.2, longitude=-5.33),
    )

    with pytest.raises(HoleMarkFarFromCourseError):
        await SaveHoleMarkUseCase(uow).execute(_request(course, hole=2, tee=None))


# ============================================================================
# U7 — Campos que no ven los jugadores
# ============================================================================


async def _hidden_course(kind: str):
    uow = InMemoryGolfCourseUnitOfWork()
    course = _course()
    if kind == "pending":
        course = GolfCourse.create(
            name="Pendiente",
            country_code=CountryCode("ES"),
            course_type=CourseType.STANDARD_18,
            creator_id=UserId.generate(),
            tees=course.tees,
            holes=[Hole(number=i + 1, par=4, stroke_index=i + 1, meters=350) for i in range(18)],
        )
    elif kind == "rejected":
        course = GolfCourse.create(
            name="Rechazado",
            country_code=CountryCode("ES"),
            course_type=CourseType.STANDARD_18,
            creator_id=UserId.generate(),
            tees=course.tees,
            holes=[Hole(number=i + 1, par=4, stroke_index=i + 1, meters=350) for i in range(18)],
        )
        course.reject("El campo no existe en la realidad")
    await uow.golf_courses.save(course)
    return uow, course


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["pending", "rejected"])
async def test_u7_courses_players_cannot_see_are_not_found(kind):
    """
    GIVEN: Un campo pendiente (como el clon de una propuesta de cambio) y uno rechazado
    WHEN: Se marca o se piden las marcas
    THEN: GolfCourseNotFoundError, como si no existiera
    """
    uow, course = await _hidden_course(kind)

    with pytest.raises(GolfCourseNotFoundError):
        await SaveHoleMarkUseCase(uow).execute(_request(course))
    with pytest.raises(GolfCourseNotFoundError):
        await _mine(uow, course)


# ============================================================================
# U8 — La cola sin cobertura: gana la más reciente para el jugador
# ============================================================================


@pytest.mark.asyncio
async def test_u8_an_older_mark_arriving_late_does_not_replace_a_newer_one():
    """
    GIVEN: El jugador marcó el hoyo 1 hace 5 minutos (la marca B, ya guardada)
    WHEN: Llega de la cola la marca A, que hizo hace 20 minutos
    THEN: Se queda B, y es la que se devuelve
    """
    uow, course = await _setup()
    use_case = SaveHoleMarkUseCase(uow)
    ahora = datetime.now(UTC)
    otro_green = (GREEN[0] + 0.0005, GREEN[1])
    await use_case.execute(
        _request(course, green=otro_green, marked_at=ahora - timedelta(minutes=5))
    )

    dto = await use_case.execute(_request(course, marked_at=ahora - timedelta(minutes=20)))

    assert dto.green_center == _p(otro_green)
    (guardada,) = await _mine(uow, course)
    assert guardada.green_center == _p(otro_green)


@pytest.mark.asyncio
async def test_u8_a_newer_mark_replaces_and_its_time_is_kept():
    """
    GIVEN: Una marca guardada hecha hace 20 minutos
    WHEN: Llega otra hecha hace 5
    THEN: La sustituye, y su fecha es la del jugador (en UTC sin zona)
    """
    uow, course = await _setup()
    use_case = SaveHoleMarkUseCase(uow)
    ahora = datetime.now(UTC)
    await use_case.execute(_request(course, marked_at=ahora - timedelta(minutes=20)))

    dto = await use_case.execute(
        _request(course, bends=[CODO], marked_at=ahora - timedelta(minutes=5))
    )

    assert dto.bends == [_p(CODO)]
    assert dto.marked_at == (ahora - timedelta(minutes=5)).replace(tzinfo=None)


@pytest.mark.asyncio
async def test_u8_a_clock_ahead_counts_as_now():
    """
    GIVEN: Un móvil con el reloj una hora adelantado
    WHEN: Marca, y luego llega una marca hecha hace 1 minuto
    THEN: La primera se guardó con la hora del servidor, y la segunda (posterior a esa) la sustituye
    """
    uow, course = await _setup()
    use_case = SaveHoleMarkUseCase(uow)
    primera = await use_case.execute(
        _request(course, marked_at=datetime.now(UTC) + timedelta(hours=1))
    )
    assert primera.marked_at <= datetime.now(UTC).replace(tzinfo=None)

    otro_green = (GREEN[0] + 0.0005, GREEN[1])
    dto = await use_case.execute(_request(course, green=otro_green))

    assert dto.green_center == _p(otro_green)


@pytest.mark.asyncio
async def test_u3_on_a_hole_with_tee_a_broken_tee_in_the_mark_does_not_lose_the_green():
    """
    GIVEN: Un hoyo con salida aprobada
    WHEN: Llega una marca con una salida imposible (latitud 95) y un codo, y un green bueno
    THEN: Se guarda el green: la salida y los codos se descartan sin mirarlos
    """
    uow, course = await _setup(map_status=HoleMapStatus.APPROVED, holes=[(2, False)])
    request = _request(course, hole=2, bends=[CODO]).model_copy(
        update={"tee": PointDTO(latitude=95, longitude=0)}
    )

    dto = await SaveHoleMarkUseCase(uow).execute(request)

    assert (dto.tee, dto.green_center) == (None, _p(GREEN))
