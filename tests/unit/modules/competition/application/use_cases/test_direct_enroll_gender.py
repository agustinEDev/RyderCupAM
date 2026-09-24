"""
Inscribir directamente exige el género del jugador (#710, 24 sep).

Las barras se valoran por género: sin él, al generar los partidos se bloqueaba
la sesión entera. Se exige al entrar, por cualquiera de los caminos.
"""

from datetime import date, timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest

from src.modules.competition.application.dto.enrollment_dto import (
    DirectEnrollPlayerRequestDTO,
)
from src.modules.competition.application.services.genero_obligatorio import GenderRequiredError
from src.modules.competition.application.use_cases.direct_enroll_player_use_case import (
    DirectEnrollPlayerUseCase,
)
from src.modules.competition.domain.entities.competition import Competition
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.competition_name import CompetitionName
from src.modules.competition.domain.value_objects.competition_status import CompetitionStatus
from src.modules.competition.domain.value_objects.date_range import DateRange
from src.modules.competition.domain.value_objects.location import Location
from src.modules.competition.domain.value_objects.play_mode import PlayMode
from src.modules.competition.infrastructure.persistence.in_memory.in_memory_unit_of_work import (
    InMemoryUnitOfWork,
)
from src.modules.user.domain.value_objects.user_id import UserId
from src.shared.domain.value_objects.country_code import CountryCode
from src.shared.domain.value_objects.gender import Gender

pytestmark = pytest.mark.asyncio


class _Usuarios:
    def __init__(self, genero):
        self._genero = genero

    async def find_by_id(self, user_id):
        return SimpleNamespace(id=user_id, gender=self._genero)


async def _abierta(uow, organizador: UserId) -> Competition:
    empieza = date.today() + timedelta(days=5)
    competicion = Competition(
        id=CompetitionId.generate(),
        creator_id=organizador,
        name=CompetitionName("Ryder del club"),
        dates=DateRange(empieza, empieza + timedelta(days=1)),
        location=Location(CountryCode("ES")),
        team_1_name="Europa",
        team_2_name="América",
        play_mode=PlayMode.SCRATCH,
        max_players=12,
        status=CompetitionStatus.ACTIVE,
    )
    async with uow:
        await uow.competitions.add(competicion)
    return competicion


async def test_g3_sin_genero_no_se_inscribe_y_lo_dice():
    uow = InMemoryUnitOfWork()
    organizador = UserId(uuid4())
    competicion = await _abierta(uow, organizador)
    jugador = UserId(uuid4())

    with pytest.raises(GenderRequiredError, match="no tiene el género en su perfil"):
        await DirectEnrollPlayerUseCase(uow, _Usuarios(None)).execute(
            DirectEnrollPlayerRequestDTO(
                competition_id=competicion.id.value, user_id=jugador.value
            ),
            organizador,
        )

    async with uow:
        assert await uow.enrollments.find_by_user_and_competition(jugador, competicion.id) is None


async def test_g3b_con_genero_se_inscribe():
    uow = InMemoryUnitOfWork()
    organizador = UserId(uuid4())
    competicion = await _abierta(uow, organizador)

    respuesta = await DirectEnrollPlayerUseCase(uow, _Usuarios(Gender.FEMALE)).execute(
        DirectEnrollPlayerRequestDTO(competition_id=competicion.id.value, user_id=uuid4()),
        organizador,
    )

    assert respuesta.status == "APPROVED"
