"""
La lectura bloqueada de una invitación (BE #359, CodeRabbit en la #488).

Retirar y aceptar a la vez leían las dos la invitación PENDING sin bloquearla:
quedaba un jugador inscrito con la invitación retirada. Ahora deciden con la
invitación releída con su fila bloqueada. En memoria no se ve: no hay
transacciones.
"""

from datetime import timedelta
from uuid import uuid4

import pytest
from sqlalchemy import text

from src.modules.competition.domain.entities.competition import Competition
from src.modules.competition.domain.entities.invitation import Invitation
from src.modules.competition.domain.value_objects.competition_id import CompetitionId
from src.modules.competition.domain.value_objects.competition_name import CompetitionName
from src.modules.competition.domain.value_objects.date_range import DateRange
from src.modules.competition.domain.value_objects.invitation_id import InvitationId
from src.modules.competition.domain.value_objects.location import Location
from src.modules.competition.infrastructure.persistence.sqlalchemy.competition_repository import (
    SQLAlchemyCompetitionRepository,
)
from src.modules.competition.infrastructure.persistence.sqlalchemy.invitation_repository import (
    SQLAlchemyInvitationRepository,
)
from src.shared.domain.value_objects.country_code import CountryCode
from src.shared.domain.value_objects.play_mode import PlayMode
from tests.integration.modules.competition.infrastructure.persistence.sqlalchemy.test_match_repository_for_update import (  # noqa: F401
    BASE_DATE,
    _esta_bloqueada,
    creator_id,
)

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


async def _invitacion(db_session, creator_id) -> Invitation:  # noqa: F811
    competition = Competition.create(
        id=CompetitionId(uuid4()),
        creator_id=creator_id,
        name=CompetitionName(f"Invitaciones {uuid4().hex[:6]}"),
        dates=DateRange(start_date=BASE_DATE, end_date=BASE_DATE + timedelta(days=1)),
        location=Location(main_country=CountryCode("ES")),
        play_mode=PlayMode.SCRATCH,
        team_1_name="Team A",
        team_2_name="Team B",
    )
    await SQLAlchemyCompetitionRepository(db_session).add(competition)
    invitacion = Invitation.create(
        id=InvitationId.generate(),
        competition_id=competition.id,
        inviter_id=creator_id,
        invitee_email=f"{uuid4().hex[:8]}@test.com",
    )
    await SQLAlchemyInvitationRepository(db_session).add(invitacion)
    await db_session.commit()
    db_session.expunge_all()
    return invitacion


async def test_bloquea_la_fila_de_la_invitacion(db_session, creator_id):  # noqa: F811
    creada = await _invitacion(db_session, creator_id)

    leida = await SQLAlchemyInvitationRepository(db_session).find_by_id_for_update(creada.id)

    assert leida.id == creada.id
    assert await _esta_bloqueada(db_session, "invitations", creada.id.value) is True


async def test_trae_el_estado_de_la_base_de_datos_no_el_que_ya_tenia(
    db_session,
    creator_id,  # noqa: F811
):
    """Sin forzar la relectura, la sesión devolvía el objeto que ya tenía, con el
    estado de ANTES: se aceptaba una invitación que otra transacción ya había retirado."""
    creada = await _invitacion(db_session, creator_id)
    repo = SQLAlchemyInvitationRepository(db_session)
    vieja = await repo.find_by_id(creada.id)
    assert vieja.status.value == "PENDING"
    # Otra conexión la retira y confirma
    async with db_session.bind.begin() as conn:
        await conn.execute(
            text("UPDATE invitations SET status = 'CANCELLED' WHERE id = :id"),
            {"id": str(creada.id.value)},
        )

    releida = await repo.find_by_id_for_update(creada.id)

    assert releida.status.value == "CANCELLED"
