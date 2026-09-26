"""
Releer una sesión bloqueada trae lo que hay en la base de datos (BE #365).

Borrar o cambiar una sesión la leía ANTES de bloquear la competición: si otra
transacción generaba sus partidos mientras tanto, se decidía con el estado
viejo y se podían borrar partidos recién hechos (CodeRabbit en la #366). Tras
el bloqueo se relee con `find_by_id_for_update`, y eso tiene que ser lo de
verdad, no lo que la sesión tuviera en memoria.
"""

import pytest
from sqlalchemy import text

from src.modules.competition.domain.value_objects.round_status import RoundStatus
from src.modules.competition.infrastructure.persistence.sqlalchemy.competition_unit_of_work import (
    SQLAlchemyCompetitionUnitOfWork,
)
from tests.integration.modules.competition.infrastructure.persistence.sqlalchemy.test_envelope_repository import (  # noqa: F401
    jugadores,
    ronda,
)

pytestmark = [pytest.mark.integration]


async def test_find_by_id_for_update_trae_lo_que_hay_en_la_base_de_datos(db_session, ronda):  # noqa: F811
    uow = SQLAlchemyCompetitionUnitOfWork(db_session)
    vieja = await uow.rounds.find_by_id(ronda.id)
    assert vieja.status == RoundStatus.PENDING_TEAMS

    # Otra conexión del mismo motor: otra transacción, como la que genera
    async with db_session.bind.begin() as conn:
        await conn.execute(
            text("UPDATE rounds SET status = 'SCHEDULED' WHERE id = :id"),
            {"id": str(ronda.id.value)},
        )

    releida = await uow.rounds.find_by_id_for_update(ronda.id)

    assert releida.status == RoundStatus.SCHEDULED
