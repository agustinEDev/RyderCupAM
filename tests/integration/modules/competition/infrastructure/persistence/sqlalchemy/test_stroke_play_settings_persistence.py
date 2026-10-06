"""
Los ajustes del stroke play se guardan y se leen (RyderCupAM#251).

Van en tres columnas de `competitions` con `composite()`, como la pieza de la
Ryder. Una Ryder las deja vacías y al leer no tiene pieza de stroke play.
"""

from datetime import timedelta
from decimal import Decimal
from uuid import uuid4

import pytest

from src.modules.competition.domain.entities.competition import Competition
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.competition_name import CompetitionName
from src.modules.competition.domain.value_objects.date_range import DateRange
from src.modules.competition.domain.value_objects.location import Location
from src.modules.competition.domain.value_objects.overall_standing import OverallStanding
from src.modules.competition.domain.value_objects.tournament_type import TournamentType
from src.modules.competition.infrastructure.persistence.sqlalchemy.competition_repository import (
    SQLAlchemyCompetitionRepository,
)
from src.shared.domain.value_objects.country_code import CountryCode
from src.shared.domain.value_objects.play_mode import PlayMode
from tests.integration.modules.competition.infrastructure.persistence.sqlalchemy.test_match_repository_for_update import (  # noqa: F401
    BASE_DATE,
    creator_id,
)

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


async def _leida(db_session, competition_id: CompetitionId) -> Competition:
    # Fuera del mapa de identidad: se lee de la base de datos de verdad
    db_session.expunge_all()
    return await SQLAlchemyCompetitionRepository(db_session).find_by_id(competition_id)


def _competicion(creator_id, **extra) -> Competition:  # noqa: F811
    return Competition.create(
        id=CompetitionId(uuid4()),
        creator_id=creator_id,
        name=CompetitionName(f"Ajustes {uuid4().hex[:6]}"),
        dates=DateRange(start_date=BASE_DATE, end_date=BASE_DATE + timedelta(days=1)),
        location=Location(main_country=CountryCode("ES")),
        play_mode=PlayMode.HANDICAP,
        **extra,
    )


async def test_un_medal_con_sus_ajustes_se_lee_igual(db_session, creator_id):  # noqa: F811
    competicion = _competicion(
        creator_id,
        tournament_type=TournamentType.MEDAL,
        category_limits=[Decimal("12.0"), Decimal("26.0")],
        max_matchdays_per_player=2,
        overall_standing=OverallStanding.BEST_CARD,
    )
    await SQLAlchemyCompetitionRepository(db_session).add(competicion)
    await db_session.commit()

    leida = await _leida(db_session, competicion.id)

    assert leida.stroke_play.category_limits == (Decimal("12.0"), Decimal("26.0"))
    assert leida.stroke_play.max_matchdays_per_player == 2
    assert leida.stroke_play.overall_standing is OverallStanding.BEST_CARD


async def test_un_stableford_sin_categorias_se_lee_sin_categorias(db_session, creator_id):  # noqa: F811
    competicion = _competicion(creator_id, tournament_type=TournamentType.STABLEFORD)
    await SQLAlchemyCompetitionRepository(db_session).add(competicion)
    await db_session.commit()

    leida = await _leida(db_session, competicion.id)

    assert leida.stroke_play.category_limits == ()
    assert leida.stroke_play.max_matchdays_per_player == 1


async def test_una_ryder_se_lee_sin_pieza_de_stroke_play(db_session, creator_id):  # noqa: F811
    competicion = _competicion(creator_id, team_1_name="Europa", team_2_name="América")
    await SQLAlchemyCompetitionRepository(db_session).add(competicion)
    await db_session.commit()

    leida = await _leida(db_session, competicion.id)

    assert leida.stroke_play is None


async def test_un_cambio_de_ajustes_queda_guardado(db_session, creator_id):  # noqa: F811
    """La pieza es inmutable y se sustituye entera: SQLAlchemy tiene que ver el cambio."""
    repo = SQLAlchemyCompetitionRepository(db_session)
    competicion = _competicion(creator_id, tournament_type=TournamentType.STABLEFORD)
    await repo.add(competicion)
    await db_session.commit()

    competicion.update_stroke_play(category_limits=[Decimal("18.0")])
    await repo.update(competicion)
    await db_session.commit()
    leida = await _leida(db_session, competicion.id)

    assert leida.stroke_play.category_limits == (Decimal("18.0"),)
