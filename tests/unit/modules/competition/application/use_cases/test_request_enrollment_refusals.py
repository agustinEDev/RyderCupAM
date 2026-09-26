"""Pedir plaza en una competición pública: el día del torneo y los «no» (BE #372).

Visto en el Kind el 24 sep: una competición que empezaba ese día rechazaba a
todo el que pedía plaza, y con un 500. Tres reglas de la política se escapaban
del caso de uso sin traducir, y un 500 llega al navegador sin cabeceras de CORS:
el modal se cerraba y el jugador no se enteraba de nada.

    #   caso                                   | qué pasa
    ----|--------------------------------------|---------------------------------
    R1  empieza hoy                            | se pide plaza (REQUESTED)
    R2  empezó ayer y sigue abierta            | EnrollmentClosedError, en español
    R3  está llena                             | CompetitionFullError, en español
    R4  quien pide ya lleva el máximo          | TooManyEnrollmentsError, en español
"""

from datetime import date, timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest

from src.modules.competition.application.dto.enrollment_dto import (
    RequestEnrollmentRequestDTO,
)
from src.modules.competition.application.services.genero_obligatorio import GenderRequiredError
from src.modules.competition.application.use_cases.request_enrollment_use_case import (
    CompetitionFullError,
    EnrollmentClosedError,
    RequestEnrollmentUseCase,
    TooManyEnrollmentsError,
)
from src.modules.competition.domain.entities.competition import Competition
from src.modules.competition.domain.entities.enrollment import Enrollment
from src.modules.competition.domain.services.competition_policy import (
    MAX_ENROLLMENTS_PER_USER,
)
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.competition_name import CompetitionName
from src.modules.competition.domain.value_objects.competition_status import (
    CompetitionStatus,
)
from src.modules.competition.domain.value_objects.date_range import DateRange
from src.modules.competition.domain.value_objects.enrollment_id import EnrollmentId
from src.modules.competition.domain.value_objects.location import Location
from src.modules.competition.domain.value_objects.play_mode import PlayMode
from src.modules.competition.domain.value_objects.visibility import Visibility
from src.modules.competition.infrastructure.persistence.in_memory.in_memory_unit_of_work import (
    InMemoryUnitOfWork,
)
from src.modules.user.domain.value_objects.user_id import UserId
from src.shared.domain.value_objects.country_code import CountryCode
from src.shared.domain.value_objects.gender import Gender

pytestmark = pytest.mark.asyncio


class _Usuarios:
    """Todos con el género dicho, o el que se diga para uno."""

    def __init__(self, genero=Gender.MALE, sin_genero=()):
        self._genero = genero
        self._sin_genero = set(sin_genero)

    async def find_by_id(self, user_id):
        genero = None if user_id in self._sin_genero else self._genero
        return SimpleNamespace(id=user_id, gender=genero)


_CON_GENERO = _Usuarios()


async def _publica(uow, empieza: date, max_players: int = 12) -> Competition:
    competicion = Competition(
        id=CompetitionId.generate(),
        creator_id=UserId(uuid4()),
        name=CompetitionName("Ryder del club"),
        dates=DateRange(empieza, empieza + timedelta(days=1)),
        location=Location(CountryCode("ES")),
        team_1_name="Europa",
        team_2_name="América",
        play_mode=PlayMode.SCRATCH,
        max_players=max_players,
        status=CompetitionStatus.ACTIVE,
        visibility=Visibility.PUBLIC,
    )
    async with uow:
        await uow.competitions.add(competicion)
    return competicion


async def _dentro(uow, competicion_id: CompetitionId, user_id: UserId | None = None) -> None:
    async with uow:
        await uow.enrollments.add(
            Enrollment.direct_enroll(
                id=EnrollmentId.generate(),
                competition_id=competicion_id,
                user_id=user_id or UserId(uuid4()),
            )
        )


def _pide(competicion: Competition, quien=None) -> RequestEnrollmentRequestDTO:
    return RequestEnrollmentRequestDTO(
        competition_id=competicion.id.value, user_id=quien or uuid4()
    )


async def test_r1_se_pide_plaza_el_mismo_dia_del_torneo():
    uow = InMemoryUnitOfWork()
    competicion = await _publica(uow, empieza=date.today())

    respuesta = await RequestEnrollmentUseCase(uow, _CON_GENERO).execute(_pide(competicion))

    assert respuesta.status == "REQUESTED"


async def test_r2_empezado_el_torneo_no_y_lo_dice():
    uow = InMemoryUnitOfWork()
    competicion = await _publica(uow, empieza=date.today() - timedelta(days=1))

    with pytest.raises(EnrollmentClosedError, match="ya ha empezado"):
        await RequestEnrollmentUseCase(uow, _CON_GENERO).execute(_pide(competicion))


async def test_r3_llena_no_y_lo_dice():
    uow = InMemoryUnitOfWork()
    competicion = await _publica(uow, empieza=date.today() + timedelta(days=3), max_players=2)
    await _dentro(uow, competicion.id)
    await _dentro(uow, competicion.id)

    with pytest.raises(CompetitionFullError, match="completa"):
        await RequestEnrollmentUseCase(uow, _CON_GENERO).execute(_pide(competicion))


async def test_r4_con_el_maximo_de_inscripciones_no_y_lo_dice():
    uow = InMemoryUnitOfWork()
    quien = UserId(uuid4())
    for _ in range(MAX_ENROLLMENTS_PER_USER):
        otra = await _publica(uow, empieza=date.today() + timedelta(days=3))
        await _dentro(uow, otra.id, quien)
    competicion = await _publica(uow, empieza=date.today() + timedelta(days=3))

    with pytest.raises(TooManyEnrollmentsError, match=str(MAX_ENROLLMENTS_PER_USER)):
        await RequestEnrollmentUseCase(uow, _CON_GENERO).execute(_pide(competicion, quien.value))


# ==================== El género es obligatorio para apuntarse (#710, 24 sep) ====================
# Las barras se valoran por género: sin él, al generar los partidos se bloqueaba
# la sesión entera. Se exige al entrar, no al final


async def test_g1_sin_genero_no_se_pide_plaza_y_lo_dice():
    uow = InMemoryUnitOfWork()
    competicion = await _publica(uow, empieza=date.today() + timedelta(days=3))
    quien = UserId(uuid4())

    with pytest.raises(GenderRequiredError, match="tu género en tu perfil"):
        await RequestEnrollmentUseCase(uow, _Usuarios(sin_genero=[quien])).execute(
            _pide(competicion, quien.value)
        )

    async with uow:
        assert await uow.enrollments.find_by_user_and_competition(quien, competicion.id) is None
