"""
Invitaciones por correo solo con el correo verificado (F-07, fase 3 del plan a 9).

Tabla aprobada el 10 nov 2026:

  D1 dirigida a la cuenta (user_id): sin cambios, verificada o no
  D2 dirigida a un correo, cuenta con ese correo VERIFICADO: la ve y la acepta
  D3 la misma con la cuenta SIN verificar: no sale en la lista y responderla da
     lo mismo que una inexistente (404), sin tocar la invitación
  D4 al verificar el correo, aparece
"""

from datetime import date, datetime, timedelta

import pytest

from src.modules.competition.application.dto.competition_dto import (
    CreateCompetitionRequestDTO,
)
from src.modules.competition.application.dto.invitation_dto import (
    RespondInvitationRequestDTO,
)
from src.modules.competition.application.exceptions import InvitationNotFoundError
from src.modules.competition.application.use_cases.create_competition_use_case import (
    CreateCompetitionUseCase,
)
from src.modules.competition.application.use_cases.list_my_invitations_use_case import (
    ListMyInvitationsUseCase,
)
from src.modules.competition.application.use_cases.respond_to_invitation_use_case import (
    RespondToInvitationUseCase,
)
from src.modules.competition.domain.entities.invitation import Invitation
from src.modules.competition.domain.services.location_builder import LocationBuilder
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.invitation_id import InvitationId
from src.modules.competition.domain.value_objects.invitation_status import InvitationStatus
from src.modules.competition.infrastructure.persistence.in_memory.in_memory_unit_of_work import (
    InMemoryUnitOfWork as CompetitionInMemoryUoW,
)
from src.modules.user.domain.entities.user import User
from src.modules.user.infrastructure.persistence.in_memory.in_memory_unit_of_work import (
    InMemoryUnitOfWork as UserInMemoryUoW,
)
from src.shared.domain.value_objects.gender import Gender
from tests.unit.modules.competition.application.use_cases.helpers import (
    USUARIOS_CON_GENERO,
    set_competition_status,
)

pytestmark = pytest.mark.asyncio

CORREO = "invitada@test.com"


@pytest.fixture
def comp_uow():
    """Competiciones en memoria."""
    return CompetitionInMemoryUoW()


@pytest.fixture
def user_uow():
    """Usuarios en memoria."""
    return UserInMemoryUoW()


async def _usuario(user_uow, email: str, verificado: bool) -> User:
    """Una cuenta guardada, con el correo verificado o sin verificar."""
    user = User.create(
        first_name="Ana",
        last_name="Lopez",
        email_str=email,
        plain_password="SecureP@ssw0rd123",
        gender=Gender.FEMALE,
    )
    if verificado:
        user.confirm_email_ownership()
    async with user_uow:
        await user_uow.users.save(user)
    return user


async def _competicion(comp_uow, creator: User):
    """Una competición activa del organizador."""
    create_uc = CreateCompetitionUseCase(
        comp_uow, LocationBuilder(comp_uow.countries), USUARIOS_CON_GENERO
    )
    request = CreateCompetitionRequestDTO(
        name="Copa Privada",
        start_date=date(2026, 6, 1),
        end_date=date(2026, 6, 3),
        main_country="ES",
        play_mode="SCRATCH",
        max_players=24,
    )
    return await create_uc.execute(request, creator.id)


async def _invitacion(comp_uow, competition_id, inviter: User, invitee_user: User | None):
    """Por correo (sin cuenta al enviarla) o, con `invitee_user`, a la cuenta."""
    invitation = Invitation.create(
        id=InvitationId.generate(),
        competition_id=CompetitionId(competition_id),
        inviter_id=inviter.id,
        invitee_email=CORREO,
        invitee_user_id=invitee_user.id if invitee_user else None,
    )
    async with comp_uow:
        await comp_uow.invitations.add(invitation)
        await comp_uow.commit()
    return invitation


async def _escenario(comp_uow, user_uow, *, verificado: bool, por_cuenta: bool = False):
    """Organizador, invitada y una invitación por correo (o a la cuenta)."""
    organizador = await _usuario(user_uow, "org@test.com", verificado=True)
    invitada = await _usuario(user_uow, CORREO, verificado=verificado)
    competicion = await _competicion(comp_uow, organizador)
    invitacion = await _invitacion(
        comp_uow, competicion.id, organizador, invitada if por_cuenta else None
    )
    return invitada, invitacion, competicion


async def _lista(comp_uow, user_uow, user: User):
    """Sus invitaciones."""
    return await ListMyInvitationsUseCase(comp_uow, user_uow).execute(user_id=str(user.id.value))


async def _responde(comp_uow, user_uow, user: User, invitation: Invitation, action: str):
    """Responde la invitación como ese usuario."""
    return await RespondToInvitationUseCase(comp_uow, user_uow).execute(
        RespondInvitationRequestDTO(
            invitation_id=invitation.id.value, user_id=user.id.value, action=action
        )
    )


async def _estado(comp_uow, invitation: Invitation) -> InvitationStatus:
    """El estado guardado de la invitación."""
    async with comp_uow:
        guardada = await comp_uow.invitations.find_by_id(invitation.id)
    return guardada.status


# ------------------------------------------------------------------ D1


async def test_d1_a_la_cuenta_sin_verificar_la_ve_y_la_acepta(comp_uow, user_uow):
    """
    Given: Una invitación dirigida a la cuenta (user_id), que no ha verificado su correo
    When: Lista sus invitaciones y la acepta
    Then: Sale en la lista y queda aceptada: por user_id no cambia nada
    """
    invitada, invitacion, _ = await _escenario(
        comp_uow, user_uow, verificado=False, por_cuenta=True
    )

    lista = await _lista(comp_uow, user_uow, invitada)
    resultado = await _responde(comp_uow, user_uow, invitada, invitacion, "ACCEPT")

    assert [i.id for i in lista.invitations] == [invitacion.id.value]
    assert resultado.status == "ACCEPTED"


# ------------------------------------------------------------------ D2


async def test_d2_por_correo_con_el_correo_verificado_la_ve(comp_uow, user_uow):
    """
    Given: Una invitación a un correo y la cuenta con ese correo verificado
    When: Lista sus invitaciones
    Then: Sale, y cuenta en el total
    """
    invitada, invitacion, _ = await _escenario(comp_uow, user_uow, verificado=True)

    lista = await _lista(comp_uow, user_uow, invitada)

    assert [i.id for i in lista.invitations] == [invitacion.id.value]
    assert lista.total_count == 1


async def test_d2_por_correo_con_el_correo_verificado_la_acepta(comp_uow, user_uow):
    """
    Given: Una invitación a un correo y la cuenta con ese correo verificado
    When: La acepta
    Then: Queda aceptada y con su inscripción
    """
    invitada, invitacion, _ = await _escenario(comp_uow, user_uow, verificado=True)

    resultado = await _responde(comp_uow, user_uow, invitada, invitacion, "ACCEPT")

    assert resultado.status == "ACCEPTED"
    assert resultado.enrollment_id is not None


# ------------------------------------------------------------------ D3


async def test_d3_sin_verificar_no_sale_en_la_lista(comp_uow, user_uow):
    """
    Given: Una invitación a un correo y la cuenta con ese correo SIN verificar
    When: Lista sus invitaciones
    Then: No sale, ni cuenta en el total
    """
    invitada, _, _ = await _escenario(comp_uow, user_uow, verificado=False)

    lista = await _lista(comp_uow, user_uow, invitada)

    assert lista.invitations == []
    assert lista.total_count == 0


@pytest.mark.parametrize("action", ["ACCEPT", "DECLINE"])
async def test_d3_sin_verificar_responderla_es_como_si_no_existiera(comp_uow, user_uow, action):
    """
    Given: Una invitación a un correo y la cuenta con ese correo SIN verificar
    When: La acepta o la rechaza
    Then: InvitationNotFoundError (el 404 de una inexistente) y sigue pendiente
    """
    invitada, invitacion, _ = await _escenario(comp_uow, user_uow, verificado=False)

    with pytest.raises(InvitationNotFoundError):
        await _responde(comp_uow, user_uow, invitada, invitacion, action)

    assert await _estado(comp_uow, invitacion) == InvitationStatus.PENDING


async def test_d3_sin_verificar_una_caducada_no_se_cierra_ni_lo_dice(comp_uow, user_uow):
    """
    Given: Una invitación por correo ya caducada y la cuenta SIN verificar
    When: La acepta
    Then: 404 como inexistente, no el «ya no está pendiente»; y no se toca
    """
    invitada, invitacion, _ = await _escenario(comp_uow, user_uow, verificado=False)
    invitacion._expires_at = datetime.now() - timedelta(days=1)
    async with comp_uow:
        await comp_uow.invitations.update(invitacion)
        await comp_uow.commit()

    with pytest.raises(InvitationNotFoundError):
        await _responde(comp_uow, user_uow, invitada, invitacion, "ACCEPT")

    assert await _estado(comp_uow, invitacion) == InvitationStatus.PENDING


async def test_d3_sin_verificar_con_la_inscripcion_cerrada_no_la_deja_sin_plaza(comp_uow, user_uow):
    """
    Given: Una invitación por correo a una competición ya cerrada, cuenta SIN verificar
    When: La acepta
    Then: 404 como inexistente, y no se queda sin plaza
    """
    invitada, invitacion, competicion = await _escenario(comp_uow, user_uow, verificado=False)
    await set_competition_status(comp_uow, competicion.id, "CLOSED")

    with pytest.raises(InvitationNotFoundError):
        await _responde(comp_uow, user_uow, invitada, invitacion, "ACCEPT")

    assert await _estado(comp_uow, invitacion) == InvitationStatus.PENDING


# ------------------------------------------------------------------ D4


async def test_d4_al_verificar_el_correo_aparece_y_se_acepta(comp_uow, user_uow):
    """
    Given: Una invitación por correo que la cuenta sin verificar no veía
    When: Verifica su correo
    Then: Aparece en la lista y la puede aceptar
    """
    invitada, invitacion, _ = await _escenario(comp_uow, user_uow, verificado=False)
    assert (await _lista(comp_uow, user_uow, invitada)).invitations == []

    invitada.confirm_email_ownership()
    async with user_uow:
        await user_uow.users.save(invitada)

    lista = await _lista(comp_uow, user_uow, invitada)
    resultado = await _responde(comp_uow, user_uow, invitada, invitacion, "ACCEPT")

    assert [i.id for i in lista.invitations] == [invitacion.id.value]
    assert resultado.status == "ACCEPTED"
