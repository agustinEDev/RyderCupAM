"""
Leer otra vez la competición en la misma sesión no cuesta consultas (27 oct 2026, PR 2).

Una petición comparte sesión entre todas sus piezas, y varias leían la misma
competición: cuatro sentencias cada vez (ella, sus campos, el campo y sus
salidas) para que SQLAlchemy devolviera el mismo objeto que ya tenía, con el
estado de antes (lo cuenta la BE #375). Si la sesión ya la tiene entera, se
devuelve sin preguntar. Si la tiene a medias (de un listado, sin los campos),
se lee: tocar los campos dispararía una carga perezosa en asíncrono.
"""

from uuid import uuid4

import pytest
from sqlalchemy import event, select

from src.modules.competition.domain.entities.competition import Competition
from src.modules.competition.infrastructure.persistence.sqlalchemy.competition_repository import (
    SQLAlchemyCompetitionRepository,
)
from tests.integration.modules.competition.infrastructure.persistence.sqlalchemy.test_competition_find_by_id_for_update import (
    _competicion_con_campo,
)
from tests.integration.modules.competition.infrastructure.persistence.sqlalchemy.test_match_repository_for_update import (  # noqa: F401
    creator_id,
    golf_course_id,
)

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


class _Cuenta:
    def __init__(self, db_session):
        self._engine = (
            db_session.bind.sync_engine
            if hasattr(db_session.bind, "sync_engine")
            else db_session.bind
        )
        self.selects = 0

    def _apunta(self, conn, cursor, statement, *args):
        if statement.lstrip().upper().startswith("SELECT"):
            self.selects += 1

    def __enter__(self):
        event.listen(self._engine, "before_cursor_execute", self._apunta)
        return self

    def __exit__(self, *exc):
        event.remove(self._engine, "before_cursor_execute", self._apunta)


async def test_la_segunda_lectura_en_la_misma_sesion_no_pregunta(
    db_session,
    creator_id,  # noqa: F811
    golf_course_id,  # noqa: F811
):
    creada = await _competicion_con_campo(db_session, creator_id, golf_course_id)
    repo = SQLAlchemyCompetitionRepository(db_session)
    primera = await repo.find_by_id(creada.id)

    with _Cuenta(db_session) as cuenta:
        segunda = await repo.find_by_id(creada.id)

    assert segunda is primera
    assert cuenta.selects == 0


async def test_a_medias_en_la_sesion_se_lee_entera(
    db_session,
    creator_id,  # noqa: F811
    golf_course_id,  # noqa: F811
):
    """Como la deja un listado: sin sus campos. Leerla tiene que traerlos."""
    creada = await _competicion_con_campo(db_session, creator_id, golf_course_id)
    await db_session.execute(select(Competition).where(Competition._id == creada.id))

    with _Cuenta(db_session) as cuenta:
        leida = await SQLAlchemyCompetitionRepository(db_session).find_by_id(creada.id)

    assert cuenta.selects > 0
    salidas = leida.golf_courses[0].golf_course.tees
    assert [(t.color.value, t.gender.value) for t in salidas] == [("YELLOW", "MALE")]


async def test_la_que_no_esta_en_la_sesion_se_lee(
    db_session,
    creator_id,  # noqa: F811
    golf_course_id,  # noqa: F811
):
    creada = await _competicion_con_campo(db_session, creator_id, golf_course_id)

    with _Cuenta(db_session) as cuenta:
        leida = await SQLAlchemyCompetitionRepository(db_session).find_by_id(creada.id)

    assert cuenta.selects > 0
    assert leida.has_golf_course(golf_course_id) is True


async def test_la_que_no_existe_sigue_siendo_none(db_session):
    from src.modules.competition.domain.value_objects.competition_id import CompetitionId

    assert (
        await SQLAlchemyCompetitionRepository(db_session).find_by_id(CompetitionId(uuid4())) is None
    )


async def test_bloqueada_se_lee_siempre(
    db_session,
    creator_id,  # noqa: F811
    golf_course_id,  # noqa: F811
):
    """La lectura con bloqueo es la que trae el estado de verdad (BE #375): siempre pregunta."""
    creada = await _competicion_con_campo(db_session, creator_id, golf_course_id)
    repo = SQLAlchemyCompetitionRepository(db_session)
    await repo.find_by_id(creada.id)

    with _Cuenta(db_session) as cuenta:
        await repo.find_by_id_for_update(creada.id)

    assert cuenta.selects > 0
