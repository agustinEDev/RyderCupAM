"""
La visibilidad de varias competiciones, sin cargar el agregado entero
(revision de la release social, 22 oct 2026): el feed solo necesita saber cuales
son privadas.
"""

from uuid import uuid4

import pytest
from sqlalchemy import text

from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.visibility import Visibility
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


async def test_devuelve_la_visibilidad_de_cada_una(db_session, creator_id, golf_course_id):  # noqa: F811
    publica = await _competicion_con_campo(db_session, creator_id, golf_course_id)
    privada = await _competicion_con_campo(db_session, creator_id, golf_course_id)
    # Una que no se pide no sale
    await _competicion_con_campo(db_session, creator_id, golf_course_id)
    for competicion, visibilidad in ((publica, "PUBLIC"), (privada, "PRIVATE")):
        await db_session.execute(
            text("UPDATE competitions SET visibility = :v WHERE id = :id"),
            {"v": visibilidad, "id": str(competicion.id.value)},
        )
    await db_session.commit()
    db_session.expunge_all()

    leidas = await SQLAlchemyCompetitionRepository(db_session).find_visibilities(
        [publica.id, privada.id, CompetitionId(uuid4())]
    )

    assert leidas == {publica.id: Visibility.PUBLIC, privada.id: Visibility.PRIVATE}


async def test_sin_ids_no_consulta(db_session):
    assert await SQLAlchemyCompetitionRepository(db_session).find_visibilities([]) == {}
