"""
Integration tests del repositorio de reportes de hoyo (entrega 7, 18 oct 2026).

Contra PostgreSQL: el reporte sale de la BD como entró, en orden de llegada;
la tabla frena lo que el dominio frena; borrar uno, los de un hoyo o el campo
entero; y dos reportes a la vez no dejan más de tres filas por hoyo.

| Caso | Situación                                         | Resultado                                  |
|------|---------------------------------------------------|--------------------------------------------|
| P1   | Dos en el hoyo 4 (con y sin codos) y uno en el 2  | Salen por hoyo y en orden de llegada, iguales |
| P2   | El mismo id otra vez                              | No entra (ON CONFLICT), y lo dice `add`    |
| P3   | Contar por hoyo y por todos los campos            | Por campo y hoyo                           |
| P4   | Borrar uno, de otro campo, y los de un hoyo       | Solo los suyos; `delete_for_hole` dice cuántos |
| P5   | Motivo que no existe, tres codos u hoyo 19        | La tabla lo rechaza                        |
| P6   | Borrar el campo                                   | Se van sus reportes                        |
| P7   | Ocho a la vez al mismo hoyo                       | Quedan tres filas                          |
"""

import asyncio
from datetime import date
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.golf_course.application.dtos.hole_report_dtos import SubmitHoleReportRequestDTO
from src.modules.golf_course.application.dtos.hole_sample_dtos import PointDTO
from src.modules.golf_course.application.use_cases.hole_report_use_cases import (
    SubmitHoleReportUseCase,
)
from src.modules.golf_course.domain.entities.hole_report import HoleReport, HoleReportReason
from src.modules.golf_course.domain.entities.saved_hole import SavedHole
from src.modules.golf_course.domain.value_objects.geo_point import GeoPoint
from src.modules.golf_course.infrastructure.persistence.repositories.hole_report_repository import (
    HoleReportRepository,
)
from src.modules.golf_course.infrastructure.persistence.repositories.saved_hole_repository import (
    SavedHoleRepository,
)
from src.modules.golf_course.infrastructure.persistence.sqlalchemy.golf_course_unit_of_work import (
    SQLAlchemyGolfCourseUnitOfWork,
)
from src.modules.golf_course.infrastructure.services.in_memory_recent_hole_sample_senders import (
    InMemoryRecentHoleSampleSenders,
)
from src.modules.user.domain.value_objects.user_id import UserId
from tests.integration.modules.golf_course.infrastructure.persistence.test_hole_map_repository import (
    _insert_user,
    _saved_course,
)
from tests.integration.modules.golf_course.infrastructure.persistence.test_hole_sample_repository import (
    _approved_course,
)

pytestmark = [pytest.mark.integration]

M_PER_DEGREE = 6_371_000.0 * 3.141592653589793 / 180
SALIDA = GeoPoint(latitude=36.28, longitude=-5.33)
CODO = GeoPoint(latitude=36.2815, longitude=-5.331)
CODO_2 = GeoPoint(latitude=36.282, longitude=-5.3312)
GREEN = GeoPoint(latitude=36.28 + 300 / M_PER_DEGREE, longitude=-5.33)
DIA = date(2026, 10, 18)


def _report(course_id, hole=1, bends=(), report_id=None, reason=HoleReportReason.WRONG_LINE):
    return HoleReport.reconstruct(
        id=report_id or uuid4(),
        golf_course_id=course_id,
        hole_number=hole,
        reason=reason,
        tee=SALIDA,
        bends=bends,
        green_center=GREEN,
        received_on=DIA,
    )


async def _course(db_session):
    creator = UserId.generate()
    await _insert_user(db_session, creator)
    return await _saved_course(db_session, creator)


@pytest.mark.asyncio
async def test_p1_round_trip_ordered_by_hole_and_arrival(db_session):
    """
    GIVEN: En el hoyo 4 uno con dos codos (el primero) y otro sin codos, y uno en el 2
    WHEN: Se leen los del campo
    THEN: Salen por hoyo y, dentro del hoyo, en orden de llegada, iguales
    """
    course_id = await _course(db_session)
    repository = HoleReportRepository(db_session)
    # Ids al revés que la llegada: el orden tiene que salir de `seq`
    antiguo = _report(
        course_id,
        hole=4,
        bends=(CODO, CODO_2),
        report_id=UUID(int=2),
        reason=HoleReportReason.HOLE_CHANGED,
    )
    nuevo = _report(course_id, hole=4, report_id=UUID(int=1))
    del_2 = _report(course_id, hole=2, reason=HoleReportReason.WRONG_HOLE)

    for report in (antiguo, nuevo, del_2):
        assert await repository.add(report) is True
    found = await repository.list_by_course(course_id)

    assert [(r.hole_number, r.id) for r in found] == [(2, del_2.id), (4, antiguo.id), (4, nuevo.id)]
    assert found[0].reason is HoleReportReason.WRONG_HOLE
    assert found[1].reason is HoleReportReason.HOLE_CHANGED
    assert (found[1].tee, found[1].bends, found[1].green_center) == (SALIDA, (CODO, CODO_2), GREEN)
    assert found[1].received_on == DIA
    assert found[2].bends == ()


@pytest.mark.asyncio
async def test_p2_the_same_id_is_not_inserted_twice(db_session):
    """
    GIVEN: Un reporte guardado
    WHEN: Se vuelve a guardar uno con el mismo id (aunque sea de otro hoyo)
    THEN: `add` dice que no entró, sin error; `exists` lo sabe
    """
    course_id = await _course(db_session)
    repository = HoleReportRepository(db_session)
    first = _report(course_id)
    assert await repository.exists(first.id) is False
    await repository.add(first)

    assert await repository.add(_report(course_id, hole=2, report_id=first.id)) is False
    assert await repository.exists(first.id) is True
    assert await repository.count_for_hole(course_id, 2) == 0


@pytest.mark.asyncio
async def test_p3_counts_per_course_and_hole(db_session):
    """
    GIVEN: Dos reportes del hoyo 1, uno del 2 y uno en otro campo
    WHEN: Se cuentan
    THEN: Dos en el 1, uno en el 2, cero en el 3; y por todos los campos, cada uno
    """
    course_id = await _course(db_session)
    otro = await _course(db_session)
    repository = HoleReportRepository(db_session)
    for report in (
        _report(course_id),
        _report(course_id),
        _report(course_id, hole=2),
        _report(otro),
    ):
        await repository.add(report)

    assert [await repository.count_for_hole(course_id, h) for h in (1, 2, 3)] == [2, 1, 0]
    mine = {(c, h): n for c, h, n in await repository.count_by_hole() if c in (course_id, otro)}
    assert mine == {(course_id, 1): 2, (course_id, 2): 1, (otro, 1): 1}


@pytest.mark.asyncio
async def test_p4_delete_one_and_delete_a_hole(db_session):
    """
    GIVEN: Tres reportes del hoyo 1 y uno del 2
    WHEN: Se borra uno desde otro campo, uno desde el suyo, y los del hoyo 1
    THEN: Desde otro campo no; desde el suyo sí; los del hoyo 1 (dos) se van y el del 2 sigue
    """
    course_id = await _course(db_session)
    otro = await _course(db_session)
    repository = HoleReportRepository(db_session)
    uno = _report(course_id)
    for report in (uno, _report(course_id), _report(course_id), _report(course_id, hole=2)):
        await repository.add(report)

    assert await repository.delete(otro, uno.id) is False
    assert await repository.delete(course_id, uno.id) is True
    assert await repository.delete_for_hole(course_id, 1) == 2

    assert [r.hole_number for r in await repository.list_by_course(course_id)] == [2]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("column", "value"),
    [
        ("reason", "'OTHER'"),
        ("hole_number", "19"),
        ("bends", "'[[1,1],[2,2],[3,3]]'::jsonb"),
    ],
    ids=["motivo", "hoyo-19", "tres-codos"],
)
async def test_p5_the_table_refuses_what_the_domain_refuses(db_session, column, value):
    """
    GIVEN: Un reporte guardado
    WHEN: Se le pone a mano un motivo que no existe, el hoyo 19 o tres codos
    THEN: La tabla lo rechaza
    """
    course_id = await _course(db_session)
    report = _report(course_id)
    await HoleReportRepository(db_session).add(report)
    await db_session.flush()

    with pytest.raises(IntegrityError):
        await db_session.execute(
            text(f"UPDATE golf_course_hole_reports SET {column} = {value} WHERE id = :id"),
            {"id": report.id},
        )


@pytest.mark.asyncio
async def test_p6_deleting_the_course_takes_its_reports(db_session):
    """
    GIVEN: Un campo con un reporte
    WHEN: Se borra el campo
    THEN: Su reporte se va con él
    """
    course_id = await _course(db_session)
    await HoleReportRepository(db_session).add(_report(course_id))
    await db_session.flush()

    await db_session.execute(
        text("DELETE FROM golf_courses WHERE id = :id"), {"id": str(course_id)}
    )

    assert await HoleReportRepository(db_session).count_for_hole(course_id, 1) == 0


@pytest.fixture
def slow_count(monkeypatch):
    """
    Ensancha la ventana entre contar y guardar: sin el bloqueo, todos los que
    llegan a la vez cuentan cero antes de que ninguno guarde (y entrarían todos).
    """
    count = HoleReportRepository.count_for_hole

    async def slow(self, *args):
        stored = await count(self, *args)
        await asyncio.sleep(0.2)
        return stored

    monkeypatch.setattr(HoleReportRepository, "count_for_hole", slow)


@pytest.mark.asyncio
async def test_p7_eight_at_once_leave_three_rows(db_session, slow_count):
    """
    GIVEN: Un hoyo con línea guardada
    WHEN: Llegan ocho reportes a la vez, de ocho jugadores, cada uno en su sesión
    THEN: Quedan tres filas: el bloqueo por hoyo no deja que se cuele un cuarto
    """
    # Aprobado: un campo que no ven los jugadores no recibe reportes
    course_id = await _approved_course(db_session)
    admin = UserId.generate()
    await _insert_user(db_session, admin)
    await SavedHoleRepository(db_session).save(
        SavedHole.create(
            golf_course_id=course_id,
            hole_number=1,
            tee=SALIDA,
            bends=(),
            green_center=GREEN,
            saved_by=admin,
            course_location=None,
        )
    )
    await db_session.commit()

    async def one() -> None:
        async with AsyncSession(bind=db_session.bind, expire_on_commit=False) as session:
            await SubmitHoleReportUseCase(
                SQLAlchemyGolfCourseUnitOfWork(session), InMemoryRecentHoleSampleSenders()
            ).execute(
                SubmitHoleReportRequestDTO(
                    id=uuid4(),
                    golf_course_id=str(course_id),
                    hole_number=1,
                    user_id=str(uuid4()),
                    reason=HoleReportReason.WRONG_LINE,
                    tee=PointDTO(latitude=SALIDA.latitude, longitude=SALIDA.longitude),
                    green_center=PointDTO(latitude=GREEN.latitude, longitude=GREEN.longitude),
                )
            )

    await asyncio.gather(*(one() for _ in range(8)))

    async with AsyncSession(bind=db_session.bind) as session:
        assert await HoleReportRepository(session).count_for_hole(course_id, 1) == 3
