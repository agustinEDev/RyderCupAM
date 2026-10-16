"""
Integration tests del repositorio de muestras anónimas de hoyo (BE #532, 16 oct 2026).

Contra PostgreSQL: lo que no se ve en memoria es que la muestra sale de la BD
como entró, que la tabla frena lo que el dominio frena, que se va con el campo,
y sobre todo que dos muestras a la vez no dejan más de tres filas (el bloqueo
consultivo por campo y hoyo).

| Caso                                              | Resultado                                  |
|---------------------------------------------------|--------------------------------------------|
| Una con dos codos y otra sin codos                | Salen igual, por hoyo y en orden de llegada |
| El orden de llegada                               | Lo da `seq`, no el id ni el día            |
| Mismo id otra vez                                 | No entra (ON CONFLICT), y lo dice `add`    |
| ¿Existe el id?                                    | Sí la guardada; no una nueva               |
| Contar                                            | Por campo y hoyo, de cualquier barra (17 oct) |
| Solo green                                        | Sale sin salida ni codos                   |
| Solo green con codos, o media salida              | La tabla lo rechaza                        |
| La barra                                          | Sale como entró (también sin género)       |
| Tres codos, hoyo 19, codos que no son una lista,  | La tabla lo rechaza                        |
| género OTHER o sin color                          |                                            |
| Borrar el campo                                   | Se van sus muestras                        |
| Ocho envíos a la vez al mismo hoyo                | Quedan tres filas                          |
| Ocho a la vez repartidos en dos hoyos             | Tres en cada uno                           |
| Un hoyo bloqueado                                 | Otro hoyo del campo no espera              |
| Ocho a la vez repartidas en dos barras            | Tres entre las dos (el tope es por hoyo)   |
| El mismo id ocho veces a la vez                   | Una fila, sin errores                      |
| El mismo jugador, tres a la vez (ids distintos)   | Una fila: la ventana se reserva a la vez   |
"""

import asyncio
from datetime import date
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.golf_course.application.dtos.hole_sample_dtos import (
    PointDTO,
    SubmitHoleSampleRequestDTO,
)
from src.modules.golf_course.application.use_cases.hole_sample_use_cases import (
    SubmitHoleSampleUseCase,
)
from src.modules.golf_course.domain.entities.golf_course import GolfCourse
from src.modules.golf_course.domain.entities.hole import Hole
from src.modules.golf_course.domain.entities.hole_sample import HoleSample
from src.modules.golf_course.domain.entities.tee import Tee
from src.modules.golf_course.domain.value_objects.course_type import CourseType
from src.modules.golf_course.domain.value_objects.geo_point import GeoPoint
from src.modules.golf_course.domain.value_objects.tee_color import TeeColor
from src.modules.golf_course.infrastructure.persistence.repositories.golf_course_repository import (
    GolfCourseRepository,
)
from src.modules.golf_course.infrastructure.persistence.repositories.hole_sample_repository import (
    HoleSampleRepository,
)
from src.modules.golf_course.infrastructure.persistence.sqlalchemy.golf_course_unit_of_work import (
    SQLAlchemyGolfCourseUnitOfWork,
)
from src.modules.golf_course.infrastructure.services.in_memory_recent_hole_sample_senders import (
    InMemoryRecentHoleSampleSenders,
)
from src.modules.user.domain.value_objects.user_id import UserId
from src.shared.domain.value_objects.country_code import CountryCode
from src.shared.domain.value_objects.gender import Gender
from tests.integration.modules.golf_course.infrastructure.persistence.test_hole_map_repository import (
    _insert_user,
    _saved_course,
)

pytestmark = [pytest.mark.integration]

M_PER_DEGREE = 6_371_000.0 * 3.141592653589793 / 180
SALIDA = GeoPoint(latitude=36.28, longitude=-5.33)
CODO = GeoPoint(latitude=36.2815, longitude=-5.331)
CODO_2 = GeoPoint(latitude=36.282, longitude=-5.3312)
GREEN = GeoPoint(latitude=36.28 + 300 / M_PER_DEGREE, longitude=-5.33)
DIA = date(2026, 10, 16)
AMARILLAS = (TeeColor.YELLOW, Gender.MALE)


def _sample(
    course_id,
    hole=1,
    bends=(),
    on=DIA,
    sample_id=None,
    color=TeeColor.YELLOW,
    gender=Gender.MALE,
    tee=SALIDA,
) -> HoleSample:
    return HoleSample.reconstruct(
        id=sample_id or uuid4(),
        golf_course_id=course_id,
        hole_number=hole,
        tee_color=color,
        tee_gender=gender,
        tee=tee,
        bends=bends,
        green_center=GREEN,
        received_on=on,
    )


async def _course(db_session):
    creator = UserId.generate()
    await _insert_user(db_session, creator)
    return await _saved_course(db_session, creator)


@pytest.mark.asyncio
async def test_r1_round_trip_ordered_by_hole_and_age(db_session):
    """
    GIVEN: En el hoyo 4 una muestra con dos codos (la primera en llegar) y otra
           después sin codos, y luego una en el hoyo 2
    WHEN: Se leen las del campo
    THEN: Salen por hoyo y, dentro del hoyo, en orden de llegada, iguales
    """
    course_id = await _course(db_session)
    repository = HoleSampleRepository(db_session)
    # Ids y días al revés que la llegada: el orden tiene que salir de `seq`
    antigua = _sample(course_id, hole=4, bends=(CODO, CODO_2), sample_id=UUID(int=2), on=DIA)
    nueva = _sample(course_id, hole=4, sample_id=UUID(int=1), on=date(2026, 10, 15))
    del_2 = _sample(course_id, hole=2)

    for sample in (antigua, nueva, del_2):
        assert await repository.add(sample) is True
    found = await repository.list_by_course(course_id)

    assert [(s.hole_number, s.id) for s in found] == [
        (2, del_2.id),
        (4, antigua.id),
        (4, nueva.id),
    ]
    assert found[1].tee == SALIDA
    assert found[1].bends == (CODO, CODO_2)
    assert found[1].green_center == GREEN
    assert found[1].received_on == DIA
    assert found[2].bends == ()


@pytest.mark.asyncio
async def test_r1_the_same_id_is_not_inserted_twice(db_session):
    """
    GIVEN: Una muestra guardada
    WHEN: Se vuelve a guardar una con el mismo id (aunque sea de otro hoyo)
    THEN: `add` dice que no entró, no hay error y sigue la primera; `exists` lo sabe
    """
    course_id = await _course(db_session)
    repository = HoleSampleRepository(db_session)
    first = _sample(course_id, bends=(CODO,))
    assert await repository.exists(first.id) is False
    await repository.add(first)

    inserted = await repository.add(_sample(course_id, hole=2, sample_id=first.id))

    assert inserted is False
    assert await repository.exists(first.id) is True
    assert await repository.count_for_hole(course_id, 2) == 0
    (kept,) = await repository.list_by_course(course_id)
    assert kept.bends == (CODO,)


@pytest.mark.asyncio
async def test_r1_count_is_per_course_and_hole(db_session):
    """
    GIVEN: Cuatro muestras del hoyo 1 desde tres barras, una del hoyo 2 y una en otro campo
    WHEN: Se cuentan por hoyo
    THEN: Cuatro en el hoyo 1, una en el 2 y cero en el 3
    """
    course_id = await _course(db_session)
    otro = await _course(db_session)
    repository = HoleSampleRepository(db_session)
    for sample in (
        _sample(course_id),
        _sample(course_id),
        _sample(course_id, gender=None),
        _sample(course_id, color=TeeColor.RED),
        _sample(course_id, hole=2),
        _sample(otro),
    ):
        await repository.add(sample)

    assert await repository.count_for_hole(course_id, 1) == 4
    assert await repository.count_for_hole(course_id, 2) == 1
    assert await repository.count_for_hole(course_id, 3) == 0


@pytest.mark.asyncio
async def test_r1_a_green_only_sample_comes_back_without_tee(db_session):
    """Una muestra solo green (17 oct) sale sin salida y sin codos."""
    course_id = await _course(db_session)
    repository = HoleSampleRepository(db_session)
    await repository.add(_sample(course_id, tee=None))

    (sample,) = await repository.list_by_course(course_id)

    assert (sample.tee, sample.bends, sample.green_center) == (None, (), GREEN)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "columns",
    [
        pytest.param("tee_latitude = NULL, tee_longitude = NULL", id="sin salida con codos"),
        pytest.param("tee_latitude = NULL", id="media salida"),
    ],
)
async def test_r1_the_table_rejects_a_broken_green_only_sample(db_session, columns):
    course_id = await _course(db_session)
    sample = _sample(course_id, bends=(CODO,))
    await HoleSampleRepository(db_session).add(sample)

    with pytest.raises(IntegrityError):
        await db_session.execute(
            text(f"UPDATE golf_course_hole_samples SET {columns} WHERE id = :id"),  # nosec B608 - columnas fijas del test
            {"id": sample.id},
        )


@pytest.mark.asyncio
async def test_r1_the_tee_comes_back(db_session):
    """
    GIVEN: Una muestra desde rojas de mujer y otra desde amarillas sin género
    WHEN: Se leen
    THEN: Cada una con su color y su género
    """
    course_id = await _course(db_session)
    repository = HoleSampleRepository(db_session)
    await repository.add(_sample(course_id, color=TeeColor.RED, gender=Gender.FEMALE))
    await repository.add(_sample(course_id, gender=None))

    found = await repository.list_by_course(course_id)

    assert [(s.tee_color, s.tee_gender) for s in found] == [
        (TeeColor.RED, Gender.FEMALE),
        (TeeColor.YELLOW, None),
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "change",
    [
        "hole_number = 19",
        "bends = '[[1,1],[2,2],[3,3]]'::jsonb",
        "bends = '{}'::jsonb",
        "tee_gender = 'OTHER'",
        "tee_color = NULL",
    ],
    ids=["hole-19", "three-bends", "not-an-array", "gender-other", "no-color"],
)
async def test_r2_the_table_rejects_what_the_domain_rejects(db_session, change):
    """
    GIVEN: Una muestra guardada
    WHEN: Se le pone a mano el hoyo 19, tres codos o unos codos que no son una lista
    THEN: La tabla lo rechaza
    """
    course_id = await _course(db_session)
    sample = _sample(course_id)
    await HoleSampleRepository(db_session).add(sample)

    with pytest.raises(IntegrityError):
        await db_session.execute(
            text(f"UPDATE golf_course_hole_samples SET {change} WHERE id = :id"),
            {"id": sample.id},
        )


@pytest.mark.asyncio
async def test_r2_samples_go_with_the_course(db_session):
    """
    GIVEN: Un campo con una muestra
    WHEN: Se borra el campo
    THEN: Se va su muestra
    """
    course_id = await _course(db_session)
    await HoleSampleRepository(db_session).add(_sample(course_id))

    await db_session.execute(
        text("DELETE FROM golf_courses WHERE id = :id"), {"id": course_id.value}
    )

    assert await HoleSampleRepository(db_session).count_for_hole(course_id, 1) == 0


# ============================================================================
# R3 — A la vez: nunca más de tres
# ============================================================================


async def _approved_course(db_session):
    """
    Un campo aprobado y confirmado, para que lo vean otras sesiones, con amarillas
    de hombre y de mujer, rojas de mujer y blancas sin género.
    """
    creator = UserId.generate()
    await _insert_user(db_session, creator)
    course = GolfCourse.create(
        name="Campo con barras",
        country_code=CountryCode("ES"),
        course_type=CourseType.STANDARD_18,
        creator_id=creator,
        tees=[
            Tee(color=c, gender=g, identifier=None, course_rating=r, slope_rating=128)
            for c, g, r in (
                (TeeColor.YELLOW, Gender.MALE, 71.0),
                (TeeColor.RED, Gender.FEMALE, 70.0),
                (TeeColor.YELLOW, Gender.FEMALE, 73.0),
                (TeeColor.WHITE, None, 72.0),
            )
        ],
        holes=[Hole(number=i + 1, par=4, stroke_index=i + 1, meters=350) for i in range(18)],
    )
    course.approve()
    await GolfCourseRepository(db_session).save(course)
    await db_session.commit()
    return course.id


async def _submit_in_own_session(
    db_session, course_id, hole: int, sample_id=None, tee=AMARILLAS, user=None, senders=None
) -> None:
    """
    Un envío como lo haría la app: su propia sesión y su unidad de trabajo. Sin
    `user`, de un jugador nuevo.
    """
    async with AsyncSession(bind=db_session.bind, expire_on_commit=False) as session:
        await SubmitHoleSampleUseCase(
            SQLAlchemyGolfCourseUnitOfWork(session),
            senders if senders is not None else InMemoryRecentHoleSampleSenders(),
        ).execute(
            SubmitHoleSampleRequestDTO(
                id=sample_id or uuid4(),
                golf_course_id=str(course_id),
                hole_number=hole,
                tee_color=tee[0],
                tee_gender=tee[1],
                user_id=user or str(uuid4()),
                tee=PointDTO(latitude=SALIDA.latitude, longitude=SALIDA.longitude),
                bends=[],
                green_center=PointDTO(latitude=GREEN.latitude, longitude=GREEN.longitude),
            )
        )


@pytest.fixture
def slow_count(monkeypatch):
    """
    Ensancha la ventana entre contar y guardar: sin el bloqueo, todas las que
    llegan a la vez cuentan cero antes de que ninguna guarde (y entrarían todas).
    """
    count = HoleSampleRepository.count_for_hole

    async def slow(self, *args):
        stored = await count(self, *args)
        await asyncio.sleep(0.2)
        return stored

    monkeypatch.setattr(HoleSampleRepository, "count_for_hole", slow)


async def _count(db_session, course_id, hole: int) -> int:
    async with AsyncSession(bind=db_session.bind) as session:
        return await HoleSampleRepository(session).count_for_hole(course_id, hole)


@pytest.mark.asyncio
async def test_r3_eight_at_once_leave_three(db_session, slow_count):
    """
    GIVEN: Un hoyo sin muestras
    WHEN: Llegan ocho a la vez, cada una en su sesión
    THEN: Quedan tres filas (sin el bloqueo, cada una contaría cero y entrarían todas)
    """
    course_id = await _approved_course(db_session)

    await asyncio.gather(*(_submit_in_own_session(db_session, course_id, 1) for _ in range(8)))

    assert await _count(db_session, course_id, 1) == 3


@pytest.mark.asyncio
async def test_r3_the_lock_is_per_hole(db_session, slow_count):
    """
    GIVEN: Dos hoyos sin muestras
    WHEN: Llegan cuatro a la vez a cada uno, mezcladas
    THEN: Tres en cada hoyo
    """
    course_id = await _approved_course(db_session)

    await asyncio.gather(
        *(_submit_in_own_session(db_session, course_id, 1 + i % 2) for i in range(8))
    )

    assert await _count(db_session, course_id, 1) == 3
    assert await _count(db_session, course_id, 2) == 3


@pytest.mark.asyncio
async def test_r3_another_hole_does_not_wait(db_session):
    """
    GIVEN: Una transacción que tiene bloqueado el hoyo 1 y no termina
    WHEN: Llega una muestra del hoyo 2 del mismo campo
    THEN: Se guarda sin esperar a que se suelte el hoyo 1
    """
    course_id = await _approved_course(db_session)

    async with AsyncSession(bind=db_session.bind) as holder:
        await HoleSampleRepository(holder).lock_hole(course_id, 1)

        await asyncio.wait_for(_submit_in_own_session(db_session, course_id, 2), timeout=5)

        assert await _count(db_session, course_id, 2) == 1
        await holder.rollback()


@pytest.mark.asyncio
async def test_r3_the_same_id_eight_times_at_once_is_one_row(db_session, slow_count):
    """
    GIVEN: Un hoyo sin muestras
    WHEN: Llega ocho veces a la vez la misma muestra (mismo id), cada una en su sesión
    THEN: Una fila, y ningún envío da error
    """
    course_id = await _approved_course(db_session)
    sample_id = uuid4()

    await asyncio.gather(
        *(_submit_in_own_session(db_session, course_id, 1, sample_id) for _ in range(8))
    )

    assert await _count(db_session, course_id, 1) == 1


@pytest.mark.asyncio
async def test_r3_eight_at_once_on_two_tees_leave_three_in_the_hole(db_session, slow_count):
    """
    GIVEN: Un hoyo sin muestras
    WHEN: Llegan cuatro a la vez desde amarillas de hombre y cuatro desde rojas de mujer
    THEN: Tres entre las dos: el tope es por hoyo (17 oct)
    """
    course_id = await _approved_course(db_session)
    rojas = (TeeColor.RED, Gender.FEMALE)

    await asyncio.gather(
        *(
            _submit_in_own_session(db_session, course_id, 1, tee=AMARILLAS if i % 2 else rojas)
            for i in range(8)
        )
    )

    assert await _count(db_session, course_id, 1) == 3


@pytest.mark.asyncio
async def test_r3_the_same_player_three_at_once_is_one_row(db_session, slow_count):
    """
    GIVEN: Un hoyo sin muestras y un jugador con tres envíos en vuelo (ids distintos,
           la misma barra), en el mismo proceso
    WHEN: Llegan los tres a la vez, cada uno en su sesión
    THEN: Una fila: el primero aparta la ventana y los otros dos ya no entran
    """
    course_id = await _approved_course(db_session)
    senders = InMemoryRecentHoleSampleSenders()
    user = str(uuid4())

    await asyncio.gather(
        *(
            _submit_in_own_session(db_session, course_id, 1, user=user, senders=senders)
            for _ in range(3)
        )
    )

    assert await _count(db_session, course_id, 1) == 1
