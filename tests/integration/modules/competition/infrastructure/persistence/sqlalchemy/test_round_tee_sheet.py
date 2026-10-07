"""La hoja de salidas de una franja se guarda y se lee igual en Postgres (#251)."""

from datetime import time

import pytest

from src.modules.competition.domain.value_objects.hoja_de_salidas import HojaDeSalidas
from src.modules.competition.infrastructure.persistence.sqlalchemy.competition_unit_of_work import (
    SQLAlchemyCompetitionUnitOfWork,
)
from tests.integration.modules.competition.infrastructure.persistence.sqlalchemy.test_envelope_repository import (  # noqa: F401
    jugadores,
    ronda,
)

pytestmark = [pytest.mark.integration]


async def test_la_hoja_va_y_vuelve(db_session, ronda):  # noqa: F811
    uow = SQLAlchemyCompetitionUnitOfWork(db_session)
    hoja = HojaDeSalidas(time(15, 0), time(18, 0), 10, 4)
    # Una sesión de Ryder no la lleva: se le pone a mano, solo para guardarla
    ronda._hoja_de_salidas = hoja
    await uow.rounds.update(ronda)
    await db_session.commit()
    db_session.expunge_all()

    leida = await uow.rounds.find_by_id(ronda.id)

    assert leida.hoja_de_salidas == hoja
    assert leida.hoja_de_salidas.cupo == 76


async def test_sin_hoja_es_nula(db_session, ronda):  # noqa: F811
    leida = await SQLAlchemyCompetitionUnitOfWork(db_session).rounds.find_by_id(ronda.id)

    assert leida.hoja_de_salidas is None
