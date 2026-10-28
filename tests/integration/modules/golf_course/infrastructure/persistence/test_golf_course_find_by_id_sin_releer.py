"""
Leer otra vez un campo en la misma sesión no cuesta consultas (27 oct 2026, PR 2).

La anotación de una partida leía su campo tres veces: dos para la zona horaria
y otra para los metros. Como con la competición, el campo que la sesión ya leyó
entero (con sus salidas) se devuelve sin preguntar; a medias o borrado, se lee.
"""

import gc

import pytest
from sqlalchemy import event, select

from src.modules.golf_course.domain.entities.golf_course import GolfCourse
from src.modules.golf_course.infrastructure.persistence.mappers.golf_course_mapper import (
    golf_courses_table,
)
from src.modules.golf_course.infrastructure.persistence.repositories.golf_course_repository import (
    GolfCourseRepository,
)
from tests.integration.modules.competition.infrastructure.persistence.sqlalchemy.test_match_repository_for_update import (  # noqa: F401
    creator_id,
    golf_course_id,
)

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


class _Cuenta:
    def __init__(self, db_session):
        self._engine = db_session.bind.sync_engine
        self.selects = 0

    def _apunta(self, conn, cursor, statement, *args):
        if statement.lstrip().upper().startswith("SELECT"):
            self.selects += 1

    def __enter__(self):
        event.listen(self._engine, "before_cursor_execute", self._apunta)
        return self

    def __exit__(self, *exc):
        event.remove(self._engine, "before_cursor_execute", self._apunta)


async def test_la_segunda_lectura_en_la_misma_sesion_no_pregunta(db_session, golf_course_id):  # noqa: F811
    db_session.expunge_all()
    await GolfCourseRepository(db_session).find_by_id(golf_course_id)
    gc.collect()

    with _Cuenta(db_session) as cuenta:
        campo = await GolfCourseRepository(db_session).find_by_id(golf_course_id)

    assert cuenta.selects == 0
    assert [t.color.value for t in campo.tees] == ["YELLOW"]


async def test_a_medias_en_la_sesion_se_lee_entero(db_session, golf_course_id):  # noqa: F811
    db_session.expunge_all()
    await db_session.execute(select(GolfCourse).where(golf_courses_table.c.id == golf_course_id))

    with _Cuenta(db_session) as cuenta:
        campo = await GolfCourseRepository(db_session).find_by_id(golf_course_id)

    assert cuenta.selects > 0
    assert [t.color.value for t in campo.tees] == ["YELLOW"]


async def test_borrado_en_la_sesion_ya_no_se_devuelve(db_session, golf_course_id):  # noqa: F811
    db_session.expunge_all()
    repo = GolfCourseRepository(db_session)
    campo = await repo.find_by_id(golf_course_id)
    await db_session.delete(campo)
    await db_session.flush()

    assert await repo.find_by_id(golf_course_id) is None


async def test_caducado_tras_un_rollback_se_vuelve_a_leer(db_session, golf_course_id):  # noqa: F811
    db_session.expunge_all()
    repo = GolfCourseRepository(db_session)
    await repo.find_by_id(golf_course_id)
    await db_session.rollback()

    with _Cuenta(db_session) as cuenta:
        campo = await repo.find_by_id(golf_course_id)

    assert cuenta.selects > 0
    assert [t.color.value for t in campo.tees] == ["YELLOW"]
