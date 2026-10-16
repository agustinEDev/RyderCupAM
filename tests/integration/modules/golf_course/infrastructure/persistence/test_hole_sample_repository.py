"""
Integration tests del repositorio de muestras anónimas de hoyo (BE #532, 16 oct 2026).

Contra PostgreSQL: lo que no se ve en memoria es que la muestra sale de la BD
como entró, que la tabla frena lo que el dominio frena, que se va con el campo,
y sobre todo que dos muestras a la vez no dejan más de tres filas (el bloqueo
consultivo por campo y hoyo).

| Caso                                              | Resultado                                  |
|---------------------------------------------------|--------------------------------------------|
| Una con dos codos y otra sin codos                | Salen igual, por hoyo y de la más antigua  |
| Contar                                            | Por campo y hoyo                           |
| Tres codos, hoyo 19, codos que no son una lista   | La tabla lo rechaza (CHECK)                |
| Borrar el campo                                   | Se van sus muestras                        |
| Ocho envíos a la vez al mismo hoyo                | Quedan tres filas                          |
| Ocho a la vez repartidos en dos hoyos             | Tres en cada uno                           |
| Un hoyo bloqueado                                 | Otro hoyo del campo no espera              |
"""

import asyncio
from datetime import datetime, timedelta
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
from src.modules.golf_course.domain.entities.hole_sample import HoleSample
from src.modules.golf_course.domain.value_objects.geo_point import GeoPoint
from src.modules.golf_course.infrastructure.persistence.repositories.golf_course_repository import (
    GolfCourseRepository,
)
from src.modules.golf_course.infrastructure.persistence.repositories.hole_sample_repository import (
    HoleSampleRepository,
)
from src.modules.golf_course.infrastructure.persistence.sqlalchemy.golf_course_unit_of_work import (
    SQLAlchemyGolfCourseUnitOfWork,
)
from src.modules.user.domain.value_objects.user_id import UserId
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
PRIMERA = datetime(2026, 10, 16, 9, 0, 0, 123456)


def _sample(course_id, hole=1, bends=(), at=PRIMERA, sample_id=None) -> HoleSample:
    return HoleSample.reconstruct(
        id=sample_id or uuid4(),
        golf_course_id=course_id,
        hole_number=hole,
        tee=SALIDA,
        bends=bends,
        green_center=GREEN,
        created_at=at,
    )


async def _course(db_session):
    creator = UserId.generate()
    await _insert_user(db_session, creator)
    return await _saved_course(db_session, creator)


@pytest.mark.asyncio
async def test_r1_round_trip_ordered_by_hole_and_age(db_session):
    """
    GIVEN: En el hoyo 4 una muestra con dos codos (la más antigua) y otra más nueva
           sin codos, y una en el hoyo 2
    WHEN: Se leen las del campo
    THEN: Salen por hoyo y, dentro del hoyo, de la más antigua a la más nueva, iguales
    """
    course_id = await _course(db_session)
    repository = HoleSampleRepository(db_session)
    # Ids al revés que las fechas: el orden tiene que salir de la fecha, no del id
    antigua = _sample(course_id, hole=4, bends=(CODO, CODO_2), sample_id=UUID(int=2))
    nueva = _sample(course_id, hole=4, at=PRIMERA + timedelta(seconds=1), sample_id=UUID(int=1))
    del_2 = _sample(course_id, hole=2, at=PRIMERA + timedelta(seconds=2))

    for sample in (nueva, del_2, antigua):
        await repository.add(sample)
    found = await repository.list_by_course(course_id)

    assert [(s.hole_number, s.id) for s in found] == [
        (2, del_2.id),
        (4, antigua.id),
        (4, nueva.id),
    ]
    assert found[1].tee == SALIDA
    assert found[1].bends == (CODO, CODO_2)
    assert found[1].green_center == GREEN
    assert found[1].created_at == PRIMERA
    assert found[2].bends == ()


@pytest.mark.asyncio
async def test_r1_count_is_per_course_and_hole(db_session):
    """
    GIVEN: Dos muestras del hoyo 1, una del 2, y una del hoyo 1 en otro campo
    WHEN: Se cuentan las del hoyo 1 y del 3 del primer campo
    THEN: Dos y cero
    """
    course_id = await _course(db_session)
    otro = await _course(db_session)
    repository = HoleSampleRepository(db_session)
    for sample in (
        _sample(course_id),
        _sample(course_id),
        _sample(course_id, hole=2),
        _sample(otro),
    ):
        await repository.add(sample)

    assert await repository.count_for_hole(course_id, 1) == 2
    assert await repository.count_for_hole(course_id, 3) == 0


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "change",
    [
        "hole_number = 19",
        "bends = '[[1,1],[2,2],[3,3]]'::jsonb",
        "bends = '{}'::jsonb",
    ],
    ids=["hole-19", "three-bends", "not-an-array"],
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
    """Un campo aprobado y confirmado, para que lo vean otras sesiones."""
    course_id = await _course(db_session)
    course = await GolfCourseRepository(db_session).find_by_id(course_id)
    course.approve()
    await GolfCourseRepository(db_session).save(course)
    await db_session.commit()
    return course_id


async def _submit_in_own_session(db_session, course_id, hole: int) -> None:
    """Un envío como lo haría la app: su propia sesión y su unidad de trabajo."""
    async with AsyncSession(bind=db_session.bind, expire_on_commit=False) as session:
        await SubmitHoleSampleUseCase(SQLAlchemyGolfCourseUnitOfWork(session)).execute(
            SubmitHoleSampleRequestDTO(
                golf_course_id=str(course_id),
                hole_number=hole,
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

    async def slow(self, golf_course_id, hole_number):
        stored = await count(self, golf_course_id, hole_number)
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
