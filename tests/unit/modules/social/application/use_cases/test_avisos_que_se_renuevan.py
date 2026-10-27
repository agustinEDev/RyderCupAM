"""
Los avisos de una inscripción se renuevan (release social 2, 27 oct 2026).

Desde que una inscripción cerrada se reutiliza al volver a entrar, el mismo id
de inscripción puede recibir dos veces el mismo aviso: rechazada, vuelve a pedir
plaza, rechazada otra vez. Con la clave única (usuario, origen, tipo) el segundo
se saltaba y se quedaba el viejo, con su fecha de antes. Estos se renuevan:
el anterior se va y queda el nuevo.

Y el aviso nuevo de la PR: «el organizador te ha quitado» (N1), solo para él.
"""

from datetime import date
from uuid import uuid4

import pytest

from src.modules.social.application.use_cases.publish_competition_notices_use_case import (
    PublishCompetitionNoticesUseCase,
    TournamentRef,
)
from src.modules.social.domain.repositories.activity_event_repository_interface import (
    ActivitySlice,
)
from src.modules.social.domain.value_objects.activity_audience import (
    AUDIENCE_BY_TYPE,
    ActivityAudience,
)
from src.modules.social.domain.value_objects.activity_event_type import ActivityEventType as T
from src.modules.social.infrastructure.persistence.in_memory.in_memory_social_unit_of_work import (
    InMemorySocialUnitOfWork,
)
from src.modules.user.domain.entities.user import User
from src.modules.user.infrastructure.persistence.in_memory.in_memory_unit_of_work import (
    InMemoryUnitOfWork as UsuariosEnMemoria,
)

pytestmark = pytest.mark.asyncio

TORNEO = TournamentRef(
    competition_id=str(uuid4()),
    name="Copa X",
    start_date=date(2027, 3, 3),
    end_date=date(2027, 3, 4),
    is_public=False,
)


async def _escenario():
    social, usuarios = InMemorySocialUnitOfWork(), UsuariosEnMemoria()
    yo = User.create(
        first_name="Ana",
        last_name="Gil",
        email_str=f"renueva_{uuid4().hex[:8]}@test.com",
        plain_password="SecureP@ssw0rd123",
    )
    async with usuarios:
        await usuarios.users.save(yo)
    return social, PublishCompetitionNoticesUseCase(social, usuarios), yo


async def _de(social, yo, tipo):
    async with social:
        eventos = await social.activity_events.find_in(
            [ActivitySlice(user_ids=(yo.id,), types=frozenset(T))], limit=100
        )
    return [e for e in eventos if e.type == tipo]


AVISOS = [
    (T.ENROLLMENT_REJECTED, lambda a, yo: a.request_rejected(yo.id, TORNEO, "enr-1")),
    (T.ENROLLMENT_REQUEST_CLOSED, lambda a, yo: a.requests_closed(TORNEO, [(yo.id, "enr-1")])),
    (
        T.ENROLLMENT_APPROVED,
        lambda a, yo: a.enrolled(yo.id, TORNEO, "enr-1", accepted_request=True),
    ),
    (T.ENROLLMENT_REMOVED, lambda a, yo: a.removed(yo.id, TORNEO, "enr-1")),
]


@pytest.mark.parametrize(("tipo", "avisar"), AVISOS, ids=[t.value for t, _ in AVISOS])
async def test_el_mismo_aviso_otra_vez_deja_uno_y_es_el_nuevo(tipo, avisar):
    social, avisos, yo = await _escenario()
    await avisar(avisos, yo)
    [primero] = await _de(social, yo, tipo)

    await avisar(avisos, yo)

    [queda] = await _de(social, yo, tipo)
    assert queda.id != primero.id


async def test_n1_te_han_quitado_es_solo_para_ti_y_dice_el_torneo():
    social, avisos, yo = await _escenario()

    await avisos.removed(yo.id, TORNEO, "enr-1")

    [aviso] = await _de(social, yo, T.ENROLLMENT_REMOVED)
    assert AUDIENCE_BY_TYPE[T.ENROLLMENT_REMOVED] == ActivityAudience.SELF
    assert aviso.payload["competition_id"] == TORNEO.competition_id
    assert aviso.payload["competition_name"] == "Copa X"
    assert aviso.source_match_id == "enr-1"


async def test_n2_salir_no_se_lleva_el_aviso_de_que_te_han_quitado():
    """El orden del caso de uso: primero se va lo de estar apuntado, luego el aviso."""
    social, avisos, yo = await _escenario()
    await avisos.enrolled(yo.id, TORNEO, "enr-1", accepted_request=False)
    await avisos.left(yo.id, TORNEO.competition_id)

    await avisos.removed(yo.id, TORNEO, "enr-1")
    await avisos.left(yo.id, TORNEO.competition_id)

    assert len(await _de(social, yo, T.ENROLLMENT_REMOVED)) == 1
    assert await _de(social, yo, T.ENROLLMENT_CONFIRMED) == []


async def test_n1_si_el_torneo_se_borra_el_aviso_de_que_te_quitaron_tambien():
    social, avisos, yo = await _escenario()
    await avisos.removed(yo.id, TORNEO, "enr-1")

    await avisos.tournament_deleted(TORNEO.competition_id)

    assert await _de(social, yo, T.ENROLLMENT_REMOVED) == []
