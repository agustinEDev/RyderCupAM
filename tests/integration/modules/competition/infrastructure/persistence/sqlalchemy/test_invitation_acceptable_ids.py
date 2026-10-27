"""Las invitaciones que aun se pueden aceptar, en una consulta ligera (revision final)."""

from datetime import datetime, timedelta
from uuid import uuid4

import pytest

from src.modules.competition.domain.entities.invitation import Invitation
from src.modules.competition.domain.value_objects.invitation_id import InvitationId
from src.modules.competition.domain.value_objects.invitation_status import InvitationStatus
from src.modules.competition.infrastructure.persistence.sqlalchemy.invitation_repository import (
    SQLAlchemyInvitationRepository,
)
from tests.integration.modules.competition.infrastructure.persistence.sqlalchemy.test_competition_find_by_id_for_update import (
    _competicion_con_campo,
)
from tests.integration.modules.competition.infrastructure.persistence.sqlalchemy.test_match_repository_for_update import (  # noqa: F401
    creator_id,
    golf_course_id,
)

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]

AHORA = datetime(2026, 10, 22, 12, 0)


async def test_solo_las_pendientes_sin_caducar(db_session, creator_id, golf_course_id):  # noqa: F811
    competicion = await _competicion_con_campo(db_session, creator_id, golf_course_id)
    repo = SQLAlchemyInvitationRepository(db_session)
    ids = {}
    for nombre, status, caduca in (
        ("abierta", InvitationStatus.PENDING, AHORA + timedelta(days=1)),
        ("caducada", InvitationStatus.PENDING, AHORA - timedelta(seconds=1)),
        ("justo", InvitationStatus.PENDING, AHORA),
        ("rechazada", InvitationStatus.DECLINED, AHORA + timedelta(days=1)),
        ("otra_abierta", InvitationStatus.PENDING, AHORA + timedelta(days=1)),
    ):
        invitacion = Invitation.reconstruct(
            id=InvitationId.generate(),
            competition_id=competicion.id,
            inviter_id=creator_id,
            invitee_email=f"{nombre}@test.com",
            status=status,
            expires_at=caduca,
            created_at=AHORA - timedelta(days=2),
        )
        await repo.add(invitacion)
        ids[nombre] = invitacion.id
    await db_session.commit()

    pedidas = [ids[n] for n in ("abierta", "caducada", "justo", "rechazada")]
    abiertas = await repo.find_acceptable_ids([*pedidas, InvitationId(uuid4())], AHORA)

    assert abiertas == {ids["abierta"]}


async def test_sin_ids_no_consulta(db_session):
    assert await SQLAlchemyInvitationRepository(db_session).find_acceptable_ids([], AHORA) == set()


# Release social 2 (27 oct 2026): con la invitación pendiente, la privada se ve
async def test_competiciones_con_invitacion_pendiente_por_usuario_o_correo(
    db_session,
    creator_id,  # noqa: F811
    golf_course_id,  # noqa: F811
):
    por_usuario = await _competicion_con_campo(db_session, creator_id, golf_course_id)
    por_correo = await _competicion_con_campo(db_session, creator_id, golf_course_id)
    caducada = await _competicion_con_campo(db_session, creator_id, golf_course_id)
    rechazada = await _competicion_con_campo(db_session, creator_id, golf_course_id)
    de_otro = await _competicion_con_campo(db_session, creator_id, golf_course_id)
    repo = SQLAlchemyInvitationRepository(db_session)
    for competicion, email, invitee, status, caduca in (
        (
            por_usuario,
            "x@test.com",
            creator_id,
            InvitationStatus.PENDING,
            AHORA + timedelta(days=1),
        ),
        (por_correo, "yo@test.com", None, InvitationStatus.PENDING, AHORA + timedelta(days=1)),
        (caducada, "yo@test.com", creator_id, InvitationStatus.PENDING, AHORA),
        (
            rechazada,
            "yo@test.com",
            creator_id,
            InvitationStatus.DECLINED,
            AHORA + timedelta(days=1),
        ),
        (de_otro, "otro@test.com", None, InvitationStatus.PENDING, AHORA + timedelta(days=1)),
    ):
        await repo.add(
            Invitation.reconstruct(
                id=InvitationId.generate(),
                competition_id=competicion.id,
                inviter_id=creator_id,
                invitee_email=email,
                invitee_user_id=invitee,
                status=status,
                expires_at=caduca,
                created_at=AHORA - timedelta(days=2),
            )
        )
    await db_session.commit()

    pendientes = await repo.competiciones_con_invitacion_pendiente(
        creator_id, " Yo@Test.com ", AHORA
    )

    assert pendientes == {por_usuario.id, por_correo.id}


async def test_competiciones_con_invitacion_pendiente_sin_correo(
    db_session,
    creator_id,  # noqa: F811
    golf_course_id,  # noqa: F811
):
    competicion = await _competicion_con_campo(db_session, creator_id, golf_course_id)
    repo = SQLAlchemyInvitationRepository(db_session)
    await repo.add(
        Invitation.reconstruct(
            id=InvitationId.generate(),
            competition_id=competicion.id,
            inviter_id=creator_id,
            invitee_email="yo@test.com",
            invitee_user_id=creator_id,
            status=InvitationStatus.PENDING,
            expires_at=AHORA + timedelta(days=1),
            created_at=AHORA,
        )
    )
    await db_session.commit()

    assert await repo.competiciones_con_invitacion_pendiente(creator_id, None, AHORA) == {
        competicion.id
    }


# Aceptar desde la ficha (tabla del 27 oct 2026, filas 13-16): la pendiente de quien mira
async def test_la_pendiente_de_quien_mira_en_una_competicion(
    db_session,
    creator_id,  # noqa: F811
    golf_course_id,  # noqa: F811
):
    competicion = await _competicion_con_campo(db_session, creator_id, golf_course_id)
    otra = await _competicion_con_campo(db_session, creator_id, golf_course_id)
    repo = SQLAlchemyInvitationRepository(db_session)

    def _invitacion(comp, email, invitee, status, caduca):
        return Invitation.reconstruct(
            id=InvitationId.generate(),
            competition_id=comp.id,
            inviter_id=creator_id,
            invitee_email=email,
            invitee_user_id=invitee,
            status=status,
            expires_at=caduca,
            created_at=AHORA - timedelta(days=2),
        )

    viva = _invitacion(
        competicion, "yo@test.com", None, InvitationStatus.PENDING, AHORA + timedelta(days=1)
    )
    antigua = _invitacion(
        competicion, "yo@test.com", creator_id, InvitationStatus.PENDING, AHORA + timedelta(days=1)
    )
    antigua._created_at = AHORA - timedelta(days=5)
    # La más reciente de todas, pero ya contestada: no cuenta (revisor)
    rechazada = _invitacion(
        competicion, "yo@test.com", creator_id, InvitationStatus.DECLINED, AHORA + timedelta(days=1)
    )
    rechazada._created_at = AHORA
    for invitacion in (
        antigua,
        viva,
        rechazada,
        _invitacion(otra, "yo@test.com", creator_id, InvitationStatus.PENDING, AHORA),
    ):
        await repo.add(invitacion)
    await db_session.commit()

    # Por su correo (invitado antes de darse de alta), sin mayúsculas ni espacios
    assert (
        await repo.pendiente_de(creator_id, " Yo@Test.com ", competicion.id, AHORA)
    ).id == viva.id
    # Caducada justo ahora: ya no
    assert await repo.pendiente_de(creator_id, "yo@test.com", otra.id, AHORA) is None
    # Con dos vivas, la más reciente; sin su correo, solo la de su usuario
    assert (await repo.pendiente_de(creator_id, None, competicion.id, AHORA)).id == antigua.id
