"""
Lo que ve el organizador de una invitación (auditoría de la fase 6, B-01 y B-03).

Invitando por id se leía el correo de cualquier usuario; invitando por correo, la
respuesta decía si ese correo tenía cuenta (y de quién era). Decidido por Agustín el
14 nov 2026: por id, el nombre y nunca el correo; por correo, solo el correo tecleado,
tenga cuenta o no, hasta que el invitado responda. Y un tope por organizador: 100 por
hora, el mismo que el de cada competición (una de 200 invita en dos tandas, BE #314).

    caso                                                   | qué ve el organizador
    -------------------------------------------------------|-------------------------------
    C1 invito por id                                       | su nombre, sin correo
    C2 invito por correo a alguien con cuenta              | solo el correo tecleado
    C3 invito por correo a alguien sin cuenta              | igual que C2
    C4 invito por correo a alguien ya inscrito             | «ya está inscrito», como antes
    C5 la de correo, aceptada o rechazada                  | ya con su nombre
    C1/C2 en la lista                                      | lo mismo que al enviar
    C7 más de 100 en una hora, sumando sus competiciones   | 429 INVITATION_USER_RATE_LIMIT
"""

from datetime import date
from unittest.mock import AsyncMock

import pytest

from src.modules.competition.application.dto.competition_dto import CreateCompetitionRequestDTO
from src.modules.competition.application.dto.invitation_dto import (
    SendInvitationByEmailRequestDTO,
    SendInvitationByUserIdRequestDTO,
)
from src.modules.competition.application.use_cases.create_competition_use_case import (
    CreateCompetitionUseCase,
)
from src.modules.competition.application.use_cases.list_competition_invitations_use_case import (
    ListCompetitionInvitationsUseCase,
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
    AlreadyEnrolledInvitationViolation,
    DuplicateInvitationViolation,
    InvitationUserRateLimitViolation,
)
from src.modules.competition.domain.services.competition_policy import (
    MAX_INVITATIONS_PER_USER_PER_HOUR,
)
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
from tests.unit.modules.competition.application.use_cases.helpers import USUARIOS_CON_GENERO

pytestmark = pytest.mark.asyncio


async def _usuario(user_uow, email: str, nombre: str = "Ana") -> User:
    user = User.create(
        first_name=nombre, last_name="Golf", email_str=email, plain_password="SecureP@ssw0rd123"
    )
    user.confirm_email_ownership()
    async with user_uow:
        await user_uow.users.save(user)
    return user


async def _competicion(comp_uow, creador: User, nombre: str = "Cup") -> str:
    creada = await CreateCompetitionUseCase(
        comp_uow, LocationBuilder(comp_uow.countries), USUARIOS_CON_GENERO
    ).execute(
        CreateCompetitionRequestDTO(
            name=nombre,
            start_date=date(2026, 6, 1),
            end_date=date(2026, 6, 3),
            main_country="ES",
            play_mode="SCRATCH",
            max_players=200,
        ),
        creador.id,
    )
    return str(creada.id)


def _por_correo(comp_uow, user_uow, correo_saliente=None):
    return SendInvitationByEmailUseCase(comp_uow, user_uow, email_service=correo_saliente)


def _por_id(comp_uow, user_uow):
    return SendInvitationByUserIdUseCase(comp_uow, user_uow)


def _visible(respuesta) -> tuple:
    """Lo que dice de quién es: correo, usuario y nombre."""
    return respuesta.invitee_email, respuesta.invitee_user_id, respuesta.invitee_name


async def _lista(comp_uow, user_uow, cid: str, organizador: User):
    pagina = await ListCompetitionInvitationsUseCase(comp_uow, user_uow).execute(
        cid, str(organizador.id.value)
    )
    return {inv.id: inv for inv in pagina.invitations}


async def test_c1_by_id_shows_the_name_never_the_email():
    comp_uow, user_uow = CompetitionInMemoryUoW(), UserInMemoryUoW()
    org = await _usuario(user_uow, "org@test.com", "Org")
    bea = await _usuario(user_uow, "bea@test.com", "Bea")
    cid = await _competicion(comp_uow, org)

    r = await _por_id(comp_uow, user_uow).execute(
        SendInvitationByUserIdRequestDTO(
            competition_id=cid, inviter_id=org.id.value, invitee_user_id=bea.id.value
        )
    )

    assert r.invitee_email is None
    assert r.invitee_user_id == bea.id.value
    assert r.invitee_name
    en_la_lista = (await _lista(comp_uow, user_uow, cid, org))[r.id]
    assert en_la_lista.invitee_email is None
    assert en_la_lista.invitee_name == r.invitee_name


async def test_c2_c3_by_email_answers_the_same_with_or_without_an_account():
    comp_uow, user_uow = CompetitionInMemoryUoW(), UserInMemoryUoW()
    org = await _usuario(user_uow, "org@test.com", "Org")
    await _usuario(user_uow, "con-cuenta@test.com", "Bea")
    cid = await _competicion(comp_uow, org)
    caso = _por_correo(comp_uow, user_uow)

    con = await caso.execute(
        SendInvitationByEmailRequestDTO(
            competition_id=cid, inviter_id=org.id.value, invitee_email="con-cuenta@test.com"
        )
    )
    sin = await caso.execute(
        SendInvitationByEmailRequestDTO(
            competition_id=cid, inviter_id=org.id.value, invitee_email="sin-cuenta@test.com"
        )
    )

    assert _visible(con) == ("con-cuenta@test.com", None, None)
    assert _visible(sin) == ("sin-cuenta@test.com", None, None)
    lista = await _lista(comp_uow, user_uow, cid, org)
    assert _visible(lista[con.id]) == ("con-cuenta@test.com", None, None)


async def test_c4_by_email_to_someone_already_enrolled_says_so_like_before():
    """C4, cambiado por Agustín el 14 nov 2026: el organizador ya ve los correos de sus
    inscritos (BE #531), así que se le dice claro, como antes, y no se crea nada."""
    comp_uow, user_uow = CompetitionInMemoryUoW(), UserInMemoryUoW()
    org = await _usuario(user_uow, "org@test.com", "Org")
    bea = await _usuario(user_uow, "inscrita@test.com", "Bea")
    cid = await _competicion(comp_uow, org)
    async with comp_uow:
        await comp_uow.enrollments.save(
            Enrollment.direct_enroll(EnrollmentId.generate(), CompetitionId(cid), bea.id)
        )
    correo = AsyncMock()

    with pytest.raises(AlreadyEnrolledInvitationViolation):
        await _por_correo(comp_uow, user_uow, correo).execute(
            SendInvitationByEmailRequestDTO(
                competition_id=cid, inviter_id=org.id.value, invitee_email="inscrita@test.com"
            )
        )
    correo.send_invitation_email.assert_not_called()


async def test_a_repeated_invitation_by_id_does_not_reveal_the_email():
    """Revisor de B-01: el 409 de «ya hay una pendiente» llevaba el correo del elegido."""
    comp_uow, user_uow = CompetitionInMemoryUoW(), UserInMemoryUoW()
    org = await _usuario(user_uow, "org@test.com", "Org")
    bea = await _usuario(user_uow, "secreto@test.com", "Bea")
    cid = await _competicion(comp_uow, org)
    pedir = SendInvitationByUserIdRequestDTO(
        competition_id=cid, inviter_id=org.id.value, invitee_user_id=bea.id.value
    )
    await _por_id(comp_uow, user_uow).execute(pedir)

    with pytest.raises(DuplicateInvitationViolation) as duplicada:
        await _por_id(comp_uow, user_uow).execute(pedir)

    assert "secreto" not in str(duplicada.value)


async def test_by_email_to_an_unverified_account_answers_like_no_account():
    comp_uow, user_uow = CompetitionInMemoryUoW(), UserInMemoryUoW()
    org = await _usuario(user_uow, "org@test.com", "Org")
    sin_verificar = User.create(
        first_name="Ceci",
        last_name="Golf",
        email_str="sin-verificar@test.com",
        plain_password="SecureP@ssw0rd123",
    )
    async with user_uow:
        await user_uow.users.save(sin_verificar)
    cid = await _competicion(comp_uow, org)

    r = await _por_correo(comp_uow, user_uow).execute(
        SendInvitationByEmailRequestDTO(
            competition_id=cid, inviter_id=org.id.value, invitee_email="sin-verificar@test.com"
        )
    )

    assert _visible(r) == ("sin-verificar@test.com", None, None)


async def test_an_invitation_by_email_from_the_previous_release_still_shows_its_email():
    """Revisor: mientras convivan las dos versiones, la anterior guarda las de correo sin
    marcar. Sin usuario, es por correo: el organizador ve el correo, no nada."""
    comp_uow, user_uow = CompetitionInMemoryUoW(), UserInMemoryUoW()
    org = await _usuario(user_uow, "org@test.com", "Org")
    cid = await _competicion(comp_uow, org)
    vieja = Invitation.create(
        id=InvitationId.generate(),
        competition_id=CompetitionId(cid),
        inviter_id=org.id,
        invitee_email="vieja@test.com",
    )
    async with comp_uow:
        await comp_uow.invitations.add(vieja)

    en_la_lista = (await _lista(comp_uow, user_uow, cid, org))[vieja.id.value]

    assert _visible(en_la_lista) == ("vieja@test.com", None, None)


async def test_c5_once_answered_the_organizer_sees_the_name():
    comp_uow, user_uow = CompetitionInMemoryUoW(), UserInMemoryUoW()
    org = await _usuario(user_uow, "org@test.com", "Org")
    await _usuario(user_uow, "bea@test.com", "Bea")
    cid = await _competicion(comp_uow, org)
    r = await _por_correo(comp_uow, user_uow).execute(
        SendInvitationByEmailRequestDTO(
            competition_id=cid, inviter_id=org.id.value, invitee_email="bea@test.com"
        )
    )
    async with comp_uow:
        inv = await comp_uow.invitations.find_by_id(InvitationId(r.id))
        inv.decline()
        await comp_uow.invitations.update(inv)

    en_la_lista = (await _lista(comp_uow, user_uow, cid, org))[r.id]

    assert en_la_lista.invitee_email == "bea@test.com"
    assert en_la_lista.invitee_user_id is not None
    assert en_la_lista.invitee_name


async def test_c7_an_organizer_cannot_send_more_than_100_an_hour_across_competitions():
    comp_uow, user_uow = CompetitionInMemoryUoW(), UserInMemoryUoW()
    org = await _usuario(user_uow, "org@test.com", "Org")
    una = await _competicion(comp_uow, org, "Una")
    otra = await _competicion(comp_uow, org, "Otra")
    caso = _por_correo(comp_uow, user_uow)
    assert MAX_INVITATIONS_PER_USER_PER_HOUR == 100

    for i in range(100):
        await caso.execute(
            SendInvitationByEmailRequestDTO(
                competition_id=una if i % 2 else otra,
                inviter_id=org.id.value,
                invitee_email=f"p{i}@test.com",
            )
        )

    with pytest.raises(InvitationUserRateLimitViolation) as tope:
        await _por_id(comp_uow, user_uow).execute(
            SendInvitationByUserIdRequestDTO(
                competition_id=una,
                inviter_id=org.id.value,
                invitee_user_id=(await _usuario(user_uow, "bea@test.com", "Bea")).id.value,
            )
        )
    assert tope.value.error_code == "INVITATION_USER_RATE_LIMIT"
    assert tope.value.limit == 100

    # Y por correo, igual
    with pytest.raises(InvitationUserRateLimitViolation):
        await caso.execute(
            SendInvitationByEmailRequestDTO(
                competition_id=otra, inviter_id=org.id.value, invitee_email="otro@test.com"
            )
        )
