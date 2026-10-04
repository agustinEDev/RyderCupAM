"""
Inscribir directamente respeta el cupo (BE #325).

La inscripción directa creaba una inscripción aprobada sin mirar `max_players`:
el organizador podía pasar de las plazas del torneo, y el sorteo, la generación
de partidos y el contador «X / Y jugadores» trabajaban con más jugadores de los
declarados. Las otras dos vías —aceptar una invitación y aprobar una solicitud—
ya lo comprobaban. La fila de la competición ya se bloqueaba desde la #710.
"""

from datetime import date, timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest

from src.modules.competition.application.dto.enrollment_dto import (
    DirectEnrollPlayerRequestDTO,
)
from src.modules.competition.application.exceptions import CompetitionFullError
from src.modules.competition.application.use_cases.direct_enroll_player_use_case import (
    AlreadyEnrolledError,
    DirectEnrollPlayerUseCase,
)
from src.modules.competition.domain.entities.competition import Competition
from src.modules.competition.domain.entities.enrollment import Enrollment
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.competition_name import CompetitionName
from src.modules.competition.domain.value_objects.competition_status import CompetitionStatus
from src.modules.competition.domain.value_objects.date_range import DateRange
from src.modules.competition.domain.value_objects.enrollment_id import EnrollmentId
from src.modules.competition.domain.value_objects.location import Location
from src.modules.competition.infrastructure.persistence.in_memory.in_memory_unit_of_work import (
    InMemoryUnitOfWork,
)
from src.modules.user.domain.value_objects.user_id import UserId
from src.shared.domain.value_objects.country_code import CountryCode
from src.shared.domain.value_objects.gender import Gender
from src.shared.domain.value_objects.play_mode import PlayMode

pytestmark = pytest.mark.asyncio


class _Usuarios:
    async def find_by_id(self, user_id):
        return SimpleNamespace(id=user_id, gender=Gender.MALE)


async def _abierta(uow, organizador: UserId, plazas: int) -> Competition:
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
        max_players=plazas,
        status=CompetitionStatus.ACTIVE,
    )
    async with uow:
        await uow.competitions.add(competicion)
    return competicion


async def _con(uow, competicion: Competition, *, aprobadas: int = 0, pendientes: int = 0):
    """Llena la competición con inscripciones aprobadas y solicitudes pendientes."""
    async with uow:
        for _ in range(aprobadas):
            await uow.enrollments.add(
                Enrollment.direct_enroll(EnrollmentId.generate(), competicion.id, UserId(uuid4()))
            )
        for _ in range(pendientes):
            await uow.enrollments.add(
                Enrollment.request(EnrollmentId.generate(), competicion.id, UserId(uuid4()))
            )


async def _inscribe(uow, competicion: Competition, organizador: UserId, jugador=None):
    jugador = jugador or uuid4()
    return await DirectEnrollPlayerUseCase(uow, _Usuarios()).execute(
        DirectEnrollPlayerRequestDTO(competition_id=competicion.id.value, user_id=jugador),
        organizador,
    )


async def test_c1_con_el_cupo_lleno_no_se_inscribe():
    uow = InMemoryUnitOfWork()
    organizador = UserId(uuid4())
    competicion = await _abierta(uow, organizador, plazas=2)
    await _con(uow, competicion, aprobadas=2)
    jugador = uuid4()

    with pytest.raises(CompetitionFullError):
        await _inscribe(uow, competicion, organizador, jugador)

    async with uow:
        assert (
            await uow.enrollments.find_by_user_and_competition(UserId(jugador), competicion.id)
            is None
        )
        assert await uow.enrollments.count_approved_by_competition(competicion.id) == 2


async def test_c2_con_una_plaza_entra_uno_y_el_siguiente_ya_no():
    uow = InMemoryUnitOfWork()
    organizador = UserId(uuid4())
    competicion = await _abierta(uow, organizador, plazas=2)
    await _con(uow, competicion, aprobadas=1)

    respuesta = await _inscribe(uow, competicion, organizador)
    assert respuesta.status == "APPROVED"

    with pytest.raises(CompetitionFullError):
        await _inscribe(uow, competicion, organizador)


async def test_c3_las_solicitudes_pendientes_no_ocupan_plaza():
    uow = InMemoryUnitOfWork()
    organizador = UserId(uuid4())
    competicion = await _abierta(uow, organizador, plazas=2)
    await _con(uow, competicion, aprobadas=1, pendientes=1)

    respuesta = await _inscribe(uow, competicion, organizador)

    assert respuesta.status == "APPROVED"


async def test_c4_quien_ya_esta_inscrito_sigue_oyendo_que_ya_lo_esta():
    uow = InMemoryUnitOfWork()
    organizador = UserId(uuid4())
    competicion = await _abierta(uow, organizador, plazas=2)
    jugador = uuid4()
    await _con(uow, competicion, aprobadas=1)
    await _inscribe(uow, competicion, organizador, jugador)

    with pytest.raises(AlreadyEnrolledError):
        await _inscribe(uow, competicion, organizador, jugador)
