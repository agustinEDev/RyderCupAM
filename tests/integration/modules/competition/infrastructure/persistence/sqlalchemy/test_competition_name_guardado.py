"""
Un nombre guardado con las reglas de antes se lee tal cual (#540, /code-review).

Antes el nombre pasaba por `title()` y el mínimo de 3 se miraba sin limpiar: en
la base de datos puede haber «A» o «<B>X</B>». Si al leer se volviera a validar
con las reglas nuevas, abrir esa competición daría un 500.
"""

import pytest
from sqlalchemy import text

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


@pytest.mark.parametrize("guardado", ["A", "<B>X</B>"])
async def test_an_old_name_loads_as_it_is(db_session, creator_id, golf_course_id, guardado):  # noqa: F811
    creada = await _competicion_con_campo(db_session, creator_id, golf_course_id)
    await db_session.execute(
        text("UPDATE competitions SET name = :n WHERE id = :id"),
        {"n": guardado, "id": str(creada.id.value)},
    )
    await db_session.commit()
    db_session.expunge_all()

    leida = await SQLAlchemyCompetitionRepository(db_session).find_by_id(creada.id)

    assert leida.name.value == guardado
