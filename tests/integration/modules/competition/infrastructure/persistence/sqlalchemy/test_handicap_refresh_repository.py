"""
Los resultados del refresco de las 3:00 en Postgres, y las sesiones por días (BE #502).
"""

from datetime import UTC, date, datetime, timedelta
from uuid import uuid4

import pytest

from src.modules.competition.domain.entities.competition import Competition
from src.modules.competition.domain.entities.round import Round
from src.modules.competition.domain.services.refresco_de_handicaps_service import (
    ResultadoRefresco,
)
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.competition_name import CompetitionName
from src.modules.competition.domain.value_objects.date_range import DateRange
from src.modules.competition.domain.value_objects.location import Location
from src.modules.competition.domain.value_objects.session_type import SessionType
from src.modules.competition.infrastructure.persistence.sqlalchemy.competition_repository import (
    SQLAlchemyCompetitionRepository,
)
from src.modules.competition.infrastructure.persistence.sqlalchemy.handicap_refresh_repository import (
    SQLAlchemyHandicapRefreshRepository,
)
from src.modules.competition.infrastructure.persistence.sqlalchemy.round_repository import (
    SQLAlchemyRoundRepository,
)
from src.shared.domain.value_objects.country_code import CountryCode
from src.shared.domain.value_objects.match_format import MatchFormat
from src.shared.domain.value_objects.play_mode import PlayMode
from tests.integration.modules.competition.infrastructure.persistence.sqlalchemy.test_match_repository_for_update import (  # noqa: F401
    BASE_DATE,
    creator_id,
    golf_course_id,
)

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]

DIA = date(2030, 10, 12)
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


async def test_apunta_y_lee_el_resultado_del_dia(db_session, creator_id):  # noqa: F811
    torneo = await _torneo(db_session, creator_id)
    repo = SQLAlchemyHandicapRefreshRepository(db_session)

    await repo.apuntar(torneo, DIA, creator_id, ResultadoRefresco.FALLIDO, MOMENTO)
    await db_session.commit()

    assert await repo.del_dia(torneo, DIA) == {creator_id: ResultadoRefresco.FALLIDO}


async def test_un_reintento_sustituye_el_resultado(db_session, creator_id):  # noqa: F811
    torneo = await _torneo(db_session, creator_id)
    repo = SQLAlchemyHandicapRefreshRepository(db_session)

    await repo.apuntar(torneo, DIA, creator_id, ResultadoRefresco.FALLIDO, MOMENTO)
    await repo.apuntar(
        torneo, DIA, creator_id, ResultadoRefresco.ACTUALIZADO, MOMENTO + timedelta(minutes=15)
    )
    await db_session.commit()

    assert await repo.del_dia(torneo, DIA) == {creator_id: ResultadoRefresco.ACTUALIZADO}


async def test_otro_dia_u_otro_torneo_no_se_mezclan(db_session, creator_id):  # noqa: F811
    torneo, otro = await _torneo(db_session, creator_id), await _torneo(db_session, creator_id)
    repo = SQLAlchemyHandicapRefreshRepository(db_session)

    await repo.apuntar(torneo, DIA, creator_id, ResultadoRefresco.ACTUALIZADO, MOMENTO)
    await db_session.commit()

    assert await repo.del_dia(torneo, DIA + timedelta(days=1)) == {}
    assert await repo.del_dia(otro, DIA) == {}


async def test_las_sesiones_de_unos_dias_de_todos_los_torneos(
    db_session,
    creator_id,  # noqa: F811
    golf_course_id,  # noqa: F811
):
    torneo, otro = await _torneo(db_session, creator_id), await _torneo(db_session, creator_id)
    repo = SQLAlchemyRoundRepository(db_session)
    # Fechas lejanas para no coincidir con las de otros tests en la misma base
    dia = date(2091, 3, 3)

    def sesion(competicion, el_dia):
        return Round.create(
            competition_id=competicion,
            golf_course_id=golf_course_id,
            round_date=el_dia,
            session_type=SessionType.MORNING,
            match_format=MatchFormat.SINGLES,
        )

    hoy_1, hoy_2, manana = (
        sesion(torneo, dia),
        sesion(otro, dia),
        sesion(torneo, dia + timedelta(1)),
    )
    for s in (hoy_1, hoy_2, manana):
        await repo.add(s)
    await db_session.commit()

    encontradas = {s.id for s in await repo.find_by_dates({dia})}

    assert encontradas == {hoy_1.id, hoy_2.id}


async def test_una_vuelta_real_cableada_contra_postgres(db_session):
    """La vuelta que monta el arranque de la app recorre las consultas de verdad sin fallar."""
    from unittest.mock import AsyncMock, MagicMock

    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

    from src.config.vigilantes import vuelta_con_la_base_de_datos

    rfeg = MagicMock()
    rfeg.search_handicap = AsyncMock(return_value=None)
    fabrica = async_sessionmaker(bind=db_session.bind, class_=AsyncSession, expire_on_commit=False)

    preguntados = await vuelta_con_la_base_de_datos(fabrica, rfeg)()

    assert isinstance(preguntados, int)


async def test_con_el_candado_cogido_por_otro_proceso_la_vuelta_se_salta(db_session):
    """Dos procesos a la vez (un despliegue a las 3:00): solo uno pregunta a la RFEG."""
    from unittest.mock import AsyncMock, MagicMock

    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

    from src.config.vigilantes import CANDADO_DEL_REFRESCO, vuelta_con_la_base_de_datos

    rfeg = MagicMock()
    rfeg.search_handicap = AsyncMock(return_value=None)
    fabrica = async_sessionmaker(bind=db_session.bind, class_=AsyncSession, expire_on_commit=False)
    vuelta = vuelta_con_la_base_de_datos(fabrica, rfeg)

    async with db_session.bind.connect() as otro_proceso:
        cogido = await otro_proceso.scalar(
            text("SELECT pg_try_advisory_lock(:k)"), {"k": CANDADO_DEL_REFRESCO}
        )
        assert cogido
        try:
            assert await vuelta() is None
        finally:
            await otro_proceso.scalar(
                text("SELECT pg_advisory_unlock(:k)"), {"k": CANDADO_DEL_REFRESCO}
            )

    # Suelto, la siguiente vuelta ya se hace
    assert isinstance(await vuelta(), int)
