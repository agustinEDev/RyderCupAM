"""
Las actualizaciones de hándicaps y sus resultados por jugador, en Postgres (#251).
"""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from src.modules.competition.domain.entities.actualizacion_de_handicaps import (
    ActualizacionDeHandicaps,
    EstadoActualizacion,
    OrigenActualizacion,
)
from src.modules.competition.domain.entities.competition import Competition
from src.modules.competition.domain.services.refresco_de_handicaps_service import (
    Intento,
    ResultadoRefresco,
)
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.competition_name import CompetitionName
from src.modules.competition.domain.value_objects.date_range import DateRange
from src.modules.competition.domain.value_objects.location import Location
from src.modules.competition.infrastructure.persistence.sqlalchemy.competition_repository import (
    SQLAlchemyCompetitionRepository,
)
from src.modules.competition.infrastructure.persistence.sqlalchemy.handicap_update_repository import (
    SQLAlchemyHandicapUpdateRepository,
)
from src.shared.domain.value_objects.country_code import CountryCode
from src.shared.domain.value_objects.play_mode import PlayMode
from tests.integration.modules.competition.infrastructure.persistence.sqlalchemy.test_match_repository_for_update import (  # noqa: F401
    BASE_DATE,
    creator_id,
)

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]

MOMENTO = datetime(2030, 10, 12, 1, 0, tzinfo=UTC)


async def _torneo(db_session, creator_id) -> CompetitionId:  # noqa: F811
    competicion = Competition.create(
        id=CompetitionId(uuid4()),
        creator_id=creator_id,
        name=CompetitionName(f"Refresco {uuid4().hex[:6]}"),
        dates=DateRange(start_date=BASE_DATE, end_date=BASE_DATE + timedelta(days=1)),
        location=Location(main_country=CountryCode("ES")),
        play_mode=PlayMode.HANDICAP,
        team_1_name="Europa",
        team_2_name="América",
    )
    await SQLAlchemyCompetitionRepository(db_session).add(competicion)
    await db_session.commit()
    return competicion.id


async def test_guarda_lee_y_da_la_ultima(db_session, creator_id):  # noqa: F811
    torneo = await _torneo(db_session, creator_id)
    repo = SQLAlchemyHandicapUpdateRepository(db_session)
    primera = ActualizacionDeHandicaps.crear(torneo, OrigenActualizacion.CIERRE, MOMENTO)
    segunda = ActualizacionDeHandicaps.crear(
        torneo, OrigenActualizacion.BOTON, MOMENTO + timedelta(hours=1)
    )
    await repo.add(primera)
    await repo.add(segunda)
    primera.terminar(pendientes=1, momento=MOMENTO + timedelta(minutes=5))
    await repo.update(primera)
    await db_session.commit()

    leida = await repo.find_by_id(primera.id)
    ultima = await repo.ultima_de(torneo)

    assert leida == primera
    assert leida.estado is EstadoActualizacion.INCOMPLETA
    assert ultima == segunda
    assert await repo.ultima_de(CompetitionId(uuid4())) is None


async def test_apunta_y_lee_con_los_intentos(db_session, creator_id):  # noqa: F811
    torneo = await _torneo(db_session, creator_id)
    repo = SQLAlchemyHandicapUpdateRepository(db_session)
    una = ActualizacionDeHandicaps.crear(torneo, OrigenActualizacion.CIERRE, MOMENTO)
    otra = ActualizacionDeHandicaps.crear(torneo, OrigenActualizacion.BOTON, MOMENTO)
    await repo.add(una)
    await repo.add(otra)

    await repo.apuntar(una.id, creator_id, ResultadoRefresco.FALLIDO, MOMENTO)
    await repo.apuntar(una.id, creator_id, ResultadoRefresco.ACTUALIZADO, MOMENTO)
    await repo.apuntar(otra.id, creator_id, ResultadoRefresco.NO_ENCONTRADO, MOMENTO)
    await db_session.commit()

    assert await repo.resultados(una.id) == {creator_id: Intento(ResultadoRefresco.ACTUALIZADO, 2)}
    assert await repo.resultados(otra.id) == {
        creator_id: Intento(ResultadoRefresco.NO_ENCONTRADO, 1)
    }
