"""
La baja de un capitán deja su puesto libre (BE #320, decidido el 22 sep).

La baja sigue funcionando como siempre: nadie queda atrapado en un torneo al
que ya no puede ir. El organizador nombra a otro antes de repartir equipos.
"""

from uuid import uuid4

import pytest

from src.modules.competition.application.dto.competition_dto import NameCaptainsRequestDTO
from src.modules.competition.application.dto.enrollment_dto import WithdrawEnrollmentRequestDTO
from src.modules.competition.application.use_cases.name_captains_use_case import (
    NameCaptainsUseCase,
)
from src.modules.competition.application.use_cases.withdraw_enrollment_use_case import (
    WithdrawEnrollmentUseCase,
)
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.infrastructure.persistence.in_memory.in_memory_unit_of_work import (
    InMemoryUnitOfWork,
)
from src.modules.user.domain.value_objects.user_id import UserId
from tests.unit.modules.competition.application.use_cases.helpers import (
    create_approved_enrollment,
    create_competition,
)

pytestmark = pytest.mark.asyncio


async def _con_capitanes():
    """Abierta con Ana, Bea y Carla; Ana y Bea capitanas."""
    uow = InMemoryUnitOfWork()
    creator_id = UserId(uuid4())
    creada = await create_competition(uow, creator_id)
    ana, bea, carla = UserId(uuid4()), UserId(uuid4()), UserId(uuid4())
    inscripciones = {
        jugador: await create_approved_enrollment(uow, creada.id, jugador)
        for jugador in (ana, bea, carla)
    }
    await NameCaptainsUseCase(uow).execute(
        NameCaptainsRequestDTO(
            competition_id=creada.id, team_a_captain_id=ana.value, team_b_captain_id=bea.value
        ),
        creator_id,
    )
    return uow, CompetitionId(creada.id), inscripciones, (ana, bea, carla)


async def _retirar(uow, inscripcion, quien):
    await WithdrawEnrollmentUseCase(uow).execute(
        WithdrawEnrollmentRequestDTO(enrollment_id=inscripcion.id.value), quien
    )


async def _capitanes(uow, competition_id):
    async with uow:
        competicion = await uow.competitions.find_by_id(competition_id)
    return competicion.team_a_captain_id, competicion.team_b_captain_id


async def test_si_se_retira_la_capitana_a_su_puesto_queda_libre():
    uow, comp_id, inscripciones, (ana, bea, _) = await _con_capitanes()

    await _retirar(uow, inscripciones[ana], ana)

    assert await _capitanes(uow, comp_id) == (None, bea)


async def test_si_se_retira_la_capitana_b_su_puesto_queda_libre():
    uow, comp_id, inscripciones, (ana, bea, _) = await _con_capitanes()

    await _retirar(uow, inscripciones[bea], bea)

    assert await _capitanes(uow, comp_id) == (ana, None)


async def test_si_se_retira_otro_los_capitanes_siguen():
    uow, comp_id, inscripciones, (ana, bea, carla) = await _con_capitanes()

    await _retirar(uow, inscripciones[carla], carla)

    assert await _capitanes(uow, comp_id) == (ana, bea)


async def test_retirarse_bloquea_la_fila_de_la_competicion():
    """Si no, un capitán que se retira a la vez que lo nombran quedaría nombrado sin jugar."""
    uow, comp_id, inscripciones, (_, _, carla) = await _con_capitanes()
    llamadas = []
    original = uow.competitions.find_by_id_for_update

    async def espia(competition_id):
        llamadas.append(competition_id)
        return await original(competition_id)

    uow.competitions.find_by_id_for_update = espia

    await _retirar(uow, inscripciones[carla], carla)

    assert llamadas == [comp_id]
