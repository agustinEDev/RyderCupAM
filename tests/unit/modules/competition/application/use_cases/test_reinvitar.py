"""
Volver a invitar (release social 2, tabla del 27 oct 2026).

Una invitación rechazada, caducada, retirada o sin plaza no impide mandar otra:
eso ya era así. Lo que fallaba (R4): una pendiente que ya había caducado sin que
nadie la abriera seguía constando PENDING y bloqueaba la nueva con un 409.

| #  | Caso                                          | Resultado                          |
|----|-----------------------------------------------|------------------------------------|
| R4 | Pendiente ya caducada                         | Pasa a EXPIRED y sale la nueva     |
| -  | Pendiente vigente                             | Duplicada, como hoy                |
| R1 | Rechazada, retirada o sin plaza               | Sale la nueva, como hoy            |
Por correo y por usuario.
"""

from datetime import date, datetime, timedelta

import pytest

from src.modules.competition.application.dto.competition_dto import CreateCompetitionRequestDTO
from src.modules.competition.application.dto.invitation_dto import (
    SendInvitationByEmailRequestDTO,
    SendInvitationByUserIdRequestDTO,
)
from src.modules.competition.application.use_cases.create_competition_use_case import (
    CreateCompetitionUseCase,
)
from src.modules.competition.application.use_cases.send_invitation_by_email_use_case import (
    SendInvitationByEmailUseCase,
)
from src.modules.competition.application.use_cases.send_invitation_by_user_id_use_case import (
    SendInvitationByUserIdUseCase,
)
from src.modules.competition.domain.entities.invitation import Invitation
from src.modules.competition.domain.exceptions.competition_violations import (
    DuplicateInvitationViolation,
)
from src.modules.competition.domain.services.location_builder import LocationBuilder
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.invitation_id import InvitationId
from src.modules.competition.domain.value_objects.invitation_status import InvitationStatus
from src.modules.competition.infrastructure.persistence.in_memory.in_memory_unit_of_work import (
    InMemoryUnitOfWork as CompeticionesEnMemoria,
)
from src.modules.user.domain.entities.user import User
from src.modules.user.infrastructure.persistence.in_memory.in_memory_unit_of_work import (
    InMemoryUnitOfWork as UsuariosEnMemoria,
)
from tests.unit.modules.competition.application.use_cases.helpers import USUARIOS_CON_GENERO
from tests.unit.modules.competition.application.use_cases.test_avisos_de_actividad import (
    _Registro,
)

pytestmark = pytest.mark.asyncio

CORREO = "invitado@test.com"


async def _usuario(usuarios, correo):
    usuario = User.create(
        first_name="Ana", last_name="Gil", email_str=correo, plain_password="SecureP@ssw0rd123"
    )
    async with usuarios:
        await usuarios.users.save(usuario)
    return usuario


async def _escenario():
    uow, usuarios = CompeticionesEnMemoria(), UsuariosEnMemoria()
    organizador = await _usuario(usuarios, "org@test.com")
    invitado = await _usuario(usuarios, CORREO)
    creada = await CreateCompetitionUseCase(
        uow, LocationBuilder(uow.countries), USUARIOS_CON_GENERO
    ).execute(
        CreateCompetitionRequestDTO(
            name="Copa",
            start_date=date.today() + timedelta(days=30),
            end_date=date.today() + timedelta(days=31),
            main_country="ES",
            play_mode="SCRATCH",
            max_players=24,
        ),
        organizador.id,
    )
    return uow, usuarios, organizador, invitado, CompetitionId(creada.id)


async def _anterior(uow, competicion_id, organizador, invitado, estado, caduca) -> Invitation:
    anterior = Invitation.reconstruct(
        id=InvitationId.generate(),
        competition_id=competicion_id,
        inviter_id=organizador.id,
        invitee_email=CORREO,
        invitee_user_id=invitado.id,
        status=estado,
        expires_at=caduca,
        created_at=caduca - timedelta(days=7),
    )
    async with uow:
        await uow.invitations.add(anterior)
    return anterior


def _por_correo(uow, usuarios, competicion_id, organizador, actividad=None):
    return SendInvitationByEmailUseCase(uow, usuarios, actividad=actividad).execute(
        SendInvitationByEmailRequestDTO(
            competition_id=competicion_id.value,
            inviter_id=organizador.id.value,
            invitee_email=CORREO,
        )
    )


def _por_usuario(uow, usuarios, competicion_id, organizador, invitado, actividad=None):
    return SendInvitationByUserIdUseCase(uow, usuarios, actividad=actividad).execute(
        SendInvitationByUserIdRequestDTO(
            competition_id=competicion_id.value,
            inviter_id=organizador.id.value,
            invitee_user_id=invitado.id.value,
        )
    )


@pytest.fixture(params=["correo", "usuario"])
def manda(request):
    def _manda(uow, usuarios, competicion_id, organizador, invitado, actividad=None):
        if request.param == "correo":
            return _por_correo(uow, usuarios, competicion_id, organizador, actividad)
        return _por_usuario(uow, usuarios, competicion_id, organizador, invitado, actividad)

    return _manda


async def test_r4_una_pendiente_ya_caducada_no_impide_invitar_otra_vez(manda):
    uow, usuarios, organizador, invitado, competicion_id = await _escenario()
    anterior = await _anterior(
        uow,
        competicion_id,
        organizador,
        invitado,
        InvitationStatus.PENDING,
        datetime.now() - timedelta(hours=1),
    )

    nueva = await manda(uow, usuarios, competicion_id, organizador, invitado)

    assert nueva.status == "PENDING"
    assert nueva.id != anterior.id.value
    async with uow:
        guardada = await uow.invitations.find_by_id(anterior.id)
    assert guardada.status == InvitationStatus.EXPIRED


async def test_una_pendiente_vigente_sigue_siendo_duplicada(manda):
    uow, usuarios, organizador, invitado, competicion_id = await _escenario()
    anterior = await _anterior(
        uow,
        competicion_id,
        organizador,
        invitado,
        InvitationStatus.PENDING,
        datetime.now() + timedelta(days=3),
    )

    with pytest.raises(DuplicateInvitationViolation):
        await manda(uow, usuarios, competicion_id, organizador, invitado)

    async with uow:
        guardada = await uow.invitations.find_by_id(anterior.id)
    assert guardada.status == InvitationStatus.PENDING


@pytest.mark.parametrize(
    "estado",
    [
        InvitationStatus.DECLINED,
        InvitationStatus.EXPIRED,
        InvitationStatus.CANCELLED,
        InvitationStatus.NO_ROOM,
    ],
)
async def test_r1_tras_una_cerrada_sale_la_nueva(manda, estado):
    uow, usuarios, organizador, invitado, competicion_id = await _escenario()
    await _anterior(
        uow, competicion_id, organizador, invitado, estado, datetime.now() - timedelta(days=1)
    )

    nueva = await manda(uow, usuarios, competicion_id, organizador, invitado)

    assert nueva.status == "PENDING"


async def test_r4_y_el_aviso_de_la_caducada_se_retira(manda):
    """
    Como al caducar al leer la lista: su «te han invitado» ya no pide nada
    (CodeRabbit, el gemelo de list_competition_invitations).
    """
    uow, usuarios, organizador, invitado, competicion_id = await _escenario()
    anterior = await _anterior(
        uow,
        competicion_id,
        organizador,
        invitado,
        InvitationStatus.PENDING,
        datetime.now() - timedelta(hours=1),
    )
    registro = _Registro()

    await manda(uow, usuarios, competicion_id, organizador, invitado, registro)

    assert ("invitations_closed", [(anterior.id, invitado.id)]) in registro.avisos


async def test_una_vigente_no_cierra_nada(manda):
    uow, usuarios, organizador, invitado, competicion_id = await _escenario()
    registro = _Registro()

    await manda(uow, usuarios, competicion_id, organizador, invitado, registro)

    assert not [a for a in registro.avisos if a[0] == "invitations_closed"]
