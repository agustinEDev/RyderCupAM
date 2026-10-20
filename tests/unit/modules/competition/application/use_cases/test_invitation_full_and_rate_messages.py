"""
Lo que se dice al invitar sin plazas o con el freno por hora, y al quedarse sin plaza.

Encontrado al probar en bloque la 2.26.0 en el Kind (5 oct):

| Caso | Situación                                         | Antes                           | Ahora                                  |
|------|---------------------------------------------------|---------------------------------|----------------------------------------|
| M1   | Invitación sin plaza porque la competición se llenó | «…al cerrarse la inscripción» | «Esta invitación se quedó sin plaza»   |
| L1   | Freno por hora agotado                            | sin código, texto con el id     | código `INVITATION_RATE_LIMIT` y límite |
| O1   | Llena y con el freno agotado, por id              | 429 «espera»                    | `CompetitionFullViolation`             |
| O2   | Llena y con el freno agotado, por correo          | 429 «espera»                    | `CompetitionFullViolation`             |
| O3   | Con plazas y el freno agotado, por id             | freno                           | freno (no cambia)                      |
| O4   | Con plazas y el freno agotado, por correo         | freno                           | freno (no cambia)                      |
"""

from datetime import date

import pytest

from src.modules.competition.application.dto.competition_dto import (
    CreateCompetitionRequestDTO,
)
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
from src.modules.competition.domain.entities.enrollment import Enrollment
from src.modules.competition.domain.entities.invitation import Invitation
from src.modules.competition.domain.exceptions.competition_violations import (
    CompetitionFullViolation,
    InvitationNoRoomViolation,
    InvitationRateLimitViolation,
)
from src.modules.competition.domain.services.competition_policy import CompetitionPolicy
from src.modules.competition.domain.services.location_builder import LocationBuilder
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.enrollment_id import EnrollmentId
from src.modules.competition.domain.value_objects.invitation_id import InvitationId
from src.modules.competition.infrastructure.persistence.in_memory.in_memory_unit_of_work import (
    InMemoryUnitOfWork as CompetitionInMemoryUoW,
)
from src.modules.user.domain.entities.user import User
from src.modules.user.infrastructure.persistence.in_memory.in_memory_unit_of_work import (
    InMemoryUnitOfWork as UserInMemoryUoW,
)
from src.shared.domain.value_objects.gender import Gender
from tests.unit.modules.competition.application.use_cases.helpers import USUARIOS_CON_GENERO

# ==================== M1: el motivo vale para cerrarse y para llenarse ====================


def test_m1_sin_plaza_no_dice_que_se_cerrara_la_inscripcion():
    mensaje = str(InvitationNoRoomViolation())

    assert mensaje == "Esta invitación se quedó sin plaza"
    assert "cerr" not in mensaje


# ==================== L1: el freno lleva su código y su límite ====================


def test_l1_el_freno_lleva_codigo_y_limite():
    with pytest.raises(InvitationRateLimitViolation) as fallo:
        CompetitionPolicy.validate_invitation_rate(12, 12, CompetitionId.generate())

    assert fallo.value.error_code == "INVITATION_RATE_LIMIT"
    assert fallo.value.limit == 12


def test_l1_el_limite_es_el_efectivo_no_el_cupo():
    with pytest.raises(InvitationRateLimitViolation) as fallo:
        CompetitionPolicy.validate_invitation_rate(100, 300, CompetitionId.generate())

    assert fallo.value.limit == 100


# ==================== O1-O4: llena manda sobre el freno ====================


async def _usuario(user_uow, email):
    user = User.create(
        first_name=email.split("@")[0].capitalize(),
        last_name="Prueba",
        email_str=email,
        plain_password="SecureP@ssw0rd123",
        gender=Gender.MALE,
    )
    async with user_uow:
        await user_uow.users.save(user)
    return user


async def _montaje(lleno: bool):
    """Cupo 3 con el freno agotado (3 enviadas en la hora). Llena: 3 aprobados."""
    comp_uow, user_uow = CompetitionInMemoryUoW(), UserInMemoryUoW()
    creador = await _usuario(user_uow, "creador@test.com")
    nuevo = await _usuario(user_uow, "nuevo@test.com")
    comp = await CreateCompetitionUseCase(
        comp_uow, LocationBuilder(comp_uow.countries), USUARIOS_CON_GENERO
    ).execute(
        CreateCompetitionRequestDTO(
            name="Ryder del club",
            start_date=date(2026, 12, 1),
            end_date=date(2026, 12, 3),
            main_country="ES",
            play_mode="SCRATCH",
            max_players=3,
        ),
        creador.id,
    )
    competicion_id = CompetitionId(comp.id)
    async with comp_uow:
        for i in range(3):
            await comp_uow.invitations.add(
                Invitation.create(
                    id=InvitationId.generate(),
                    competition_id=competicion_id,
                    inviter_id=creador.id,
                    invitee_email=f"enviada{i}@test.com",
                )
            )
        # El organizador ya ocupa una al crearla: dos más la llenan
        if lleno:
            for i in range(2):
                jugador = await _usuario(user_uow, f"dentro{i}@test.com")
                await comp_uow.enrollments.add(
                    Enrollment.direct_enroll(
                        id=EnrollmentId.generate(),
                        competition_id=competicion_id,
                        user_id=jugador.id,
                    )
                )
        await comp_uow.commit()
    return comp_uow, user_uow, creador, nuevo, comp


async def _por_id(comp_uow, user_uow, creador, nuevo, comp):
    await SendInvitationByUserIdUseCase(comp_uow, user_uow).execute(
        SendInvitationByUserIdRequestDTO(
            competition_id=comp.id,
            inviter_id=creador.id.value,
            invitee_user_id=nuevo.id.value,
        )
    )


async def _por_correo(comp_uow, user_uow, creador, nuevo, comp):
    await SendInvitationByEmailUseCase(comp_uow, user_uow).execute(
        SendInvitationByEmailRequestDTO(
            competition_id=comp.id,
            inviter_id=creador.id.value,
            invitee_email=str(nuevo.email),
        )
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("enviar", [_por_id, _por_correo], ids=["O1-por-id", "O2-por-correo"])
async def test_llena_y_con_el_freno_agotado_dice_que_esta_llena(enviar):
    montaje = await _montaje(lleno=True)

    with pytest.raises(CompetitionFullViolation):
        await enviar(*montaje)


@pytest.mark.asyncio
@pytest.mark.parametrize("enviar", [_por_id, _por_correo], ids=["O3-por-id", "O4-por-correo"])
async def test_con_plazas_y_el_freno_agotado_sigue_frenando(enviar):
    montaje = await _montaje(lleno=False)

    with pytest.raises(InvitationRateLimitViolation):
        await enviar(*montaje)
