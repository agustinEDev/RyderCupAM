"""
El tipo de torneo se guarda y se lee (RyderCupAM#251).

Un Stableford o un Medal no tiene pieza de Ryder Cup: sus columnas (equipos,
modo de montaje, reparto y capitanes) se guardan vacías y al leer no hay pieza.
Las competiciones de siempre siguen siendo Ryder Cup con su pieza entera.
"""

from datetime import timedelta
from uuid import uuid4

import pytest

from src.modules.competition.domain.entities.competition import Competition
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.competition_name import CompetitionName
from src.modules.competition.domain.value_objects.date_range import DateRange
from src.modules.competition.domain.value_objects.location import Location
from src.modules.competition.domain.value_objects.setup_mode import SetupMode
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


async def _guardada_y_leida(db_session, competition: Competition) -> Competition:
    repo = SQLAlchemyCompetitionRepository(db_session)
    await repo.add(competition)
    await db_session.commit()
    # Fuera del mapa de identidad: se lee de la base de datos de verdad
    db_session.expunge_all()
    return await repo.find_by_id(competition.id)


def _competicion(creator_id, **extra) -> Competition:  # noqa: F811
    return Competition.create(
        id=CompetitionId(uuid4()),
        creator_id=creator_id,
        name=CompetitionName(f"Tipo {uuid4().hex[:6]}"),
        dates=DateRange(start_date=BASE_DATE, end_date=BASE_DATE + timedelta(days=1)),
        location=Location(main_country=CountryCode("ES")),
        play_mode=PlayMode.HANDICAP,
        **extra,
    )


@pytest.mark.parametrize("tipo", [TournamentType.STABLEFORD, TournamentType.MEDAL])
async def test_un_torneo_de_stroke_play_se_lee_sin_pieza_de_ryder_cup(
    db_session,
    creator_id,  # noqa: F811
    tipo,
):
    leida = await _guardada_y_leida(db_session, _competicion(creator_id, tournament_type=tipo))

    assert leida.tournament_type == tipo
    assert leida.ryder_cup is None


async def test_una_ryder_cup_se_lee_con_su_tipo_y_su_pieza(db_session, creator_id):  # noqa: F811
    leida = await _guardada_y_leida(
        db_session,
        _competicion(
            creator_id, team_1_name="Europa", team_2_name="América", setup_mode=SetupMode.AUTOMATIC
        ),
    )

    assert leida.tournament_type == TournamentType.RYDER_CUP
    assert (leida.ryder_cup.team_1_name, leida.ryder_cup.team_2_name) == ("Europa", "América")
    assert leida.ryder_cup.setup_mode == SetupMode.AUTOMATIC
