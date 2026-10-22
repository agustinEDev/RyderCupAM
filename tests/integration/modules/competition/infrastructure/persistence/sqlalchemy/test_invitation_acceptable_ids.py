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
