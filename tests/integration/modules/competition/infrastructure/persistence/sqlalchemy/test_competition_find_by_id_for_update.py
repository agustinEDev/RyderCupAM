"""
La lectura bloqueada de una competición trae el agregado entero (BE #370).

Crear, configurar y cambiar sesiones leen la competición con su fila bloqueada
y luego le preguntan por sus campos de golf. La lectura bloqueada no los traía:
preguntar disparaba una carga perezosa dentro de código asíncrono y reventaba
(`MissingGreenlet`). En memoria no se ve: allí el objeto siempre está completo.
"""

from datetime import timedelta
from uuid import uuid4

import pytest

from src.modules.competition.domain.entities.competition import Competition
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.competition_name import CompetitionName
from src.modules.competition.domain.value_objects.date_range import DateRange
from src.modules.competition.domain.value_objects.location import Location
from src.modules.competition.domain.value_objects.play_mode import PlayMode
from src.modules.competition.infrastructure.persistence.sqlalchemy.competition_repository import (
    SQLAlchemyCompetitionRepository,
)
from src.shared.domain.value_objects.country_code import CountryCode
from tests.integration.modules.competition.infrastructure.persistence.sqlalchemy.test_match_repository_for_update import (  # noqa: F401
    BASE_DATE,
    _esta_bloqueada,
    creator_id,
    golf_course_id,
)

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


async def _competicion_con_campo(db_session, creator_id, golf_course_id) -> Competition:  # noqa: F811
    competition = Competition.create(
        id=CompetitionId(uuid4()),
        creator_id=creator_id,
        name=CompetitionName(f"Agregado {uuid4().hex[:6]}"),
        dates=DateRange(start_date=BASE_DATE, end_date=BASE_DATE + timedelta(days=1)),
        location=Location(main_country=CountryCode("ES")),
        play_mode=PlayMode.SCRATCH,
        team_1_name="Team A",
        team_2_name="Team B",
    )
    competition.add_golf_course(golf_course_id, CountryCode("ES"))
    await SQLAlchemyCompetitionRepository(db_session).add(competition)
    await db_session.commit()
    # Fuera del mapa de identidad: la lectura tiene que traerlo todo ella
    db_session.expunge_all()
    return competition


async def test_trae_los_campos_de_golf(db_session, creator_id, golf_course_id):  # noqa: F811
    creada = await _competicion_con_campo(db_session, creator_id, golf_course_id)

    leida = await SQLAlchemyCompetitionRepository(db_session).find_by_id_for_update(creada.id)

    assert leida.has_golf_course(golf_course_id) is True


async def test_bloquea_la_fila_de_la_competicion(db_session, creator_id, golf_course_id):  # noqa: F811
    creada = await _competicion_con_campo(db_session, creator_id, golf_course_id)

    await SQLAlchemyCompetitionRepository(db_session).find_by_id_for_update(creada.id)

    assert await _esta_bloqueada(db_session, "competitions", creada.id.value) is True
