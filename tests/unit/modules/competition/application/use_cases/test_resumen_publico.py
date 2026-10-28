"""
El resumen público de una competición (release social 3, L5, 28 oct 2026).

Sin sesión, la página de la clasificación necesita saber qué pintar: una Ryder
o un stroke play, y si es privada. Sin la ficha (que pide sesión): nombre, tipo,
estado, visibilidad y fechas. También de una privada: privada no es secreta.
"""

from datetime import date, timedelta
from uuid import uuid4

import pytest

from src.modules.competition.application.exceptions import CompetitionNotFoundError
from src.modules.competition.application.use_cases.get_competition_summary_use_case import (
    GetCompetitionSummaryUseCase,
)
from src.modules.competition.domain.entities.competition import Competition
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.competition_name import CompetitionName
from src.modules.competition.domain.value_objects.competition_status import CompetitionStatus
from src.modules.competition.domain.value_objects.date_range import DateRange
from src.modules.competition.domain.value_objects.location import Location
from src.modules.competition.domain.value_objects.tournament_type import TournamentType
from src.modules.competition.domain.value_objects.visibility import Visibility
from src.modules.competition.infrastructure.persistence.in_memory.in_memory_unit_of_work import (
    InMemoryUnitOfWork,
)
from src.modules.user.domain.value_objects.user_id import UserId
from src.shared.domain.value_objects.country_code import CountryCode
from src.shared.domain.value_objects.play_mode import PlayMode

pytestmark = pytest.mark.asyncio

EMPIEZA = date(2027, 3, 3)


async def _una(uow, **datos) -> Competition:
    competicion = Competition(
        id=CompetitionId.generate(),
        creator_id=UserId(uuid4()),
        name=CompetitionName("Copa X"),
        dates=DateRange(EMPIEZA, EMPIEZA + timedelta(days=1)),
        location=Location(CountryCode("ES")),
        play_mode=PlayMode.HANDICAP,
        status=CompetitionStatus.IN_PROGRESS,
        **datos,
    )
    async with uow:
        await uow.competitions.add(competicion)
    return competicion


async def test_l5_una_ryder_publica():
    uow = InMemoryUnitOfWork()
    competicion = await _una(uow, visibility=Visibility.PUBLIC, team_1_name="A", team_2_name="B")

    resumen = await GetCompetitionSummaryUseCase(uow).execute(competicion.id.value)

    assert resumen.id == competicion.id.value
    assert resumen.name == "Copa X"
    assert resumen.tournament_type == "RYDER_CUP"
    assert resumen.has_teams is True
    assert resumen.status == "IN_PROGRESS"
    assert resumen.visibility == "PUBLIC"
    assert resumen.start_date == EMPIEZA
    assert resumen.end_date == EMPIEZA + timedelta(days=1)


async def test_l5_un_stroke_play_privado_tambien():
    uow = InMemoryUnitOfWork()
    competicion = await _una(
        uow,
        visibility=Visibility.PRIVATE,
        tournament_type=TournamentType.MEDAL,
        category_limits=[],
    )

    resumen = await GetCompetitionSummaryUseCase(uow).execute(competicion.id.value)

    assert resumen.tournament_type == "MEDAL"
    assert resumen.has_teams is False
    assert resumen.visibility == "PRIVATE"


async def test_l5_la_que_no_existe():
    with pytest.raises(CompetitionNotFoundError):
        await GetCompetitionSummaryUseCase(InMemoryUnitOfWork()).execute(uuid4())
