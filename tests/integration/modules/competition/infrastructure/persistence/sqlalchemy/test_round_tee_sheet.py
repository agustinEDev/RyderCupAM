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


async def test_esperas_y_marcas_de_la_plaza(db_session, ronda, jugadores):  # noqa: F811
    """La lista de espera y las marcas «desde la lista» y «vista», en Postgres (#251)."""
    from datetime import UTC, datetime

    from src.modules.competition.domain.entities.espera_en_franja import EsperaEnFranja
    from src.modules.competition.domain.entities.plaza_en_franja import PlazaEnFranja

    uow = SQLAlchemyCompetitionUnitOfWork(db_session)
    ahora = datetime(2030, 10, 10, 18, 0, tzinfo=UTC)
    primero, segundo = jugadores[0], jugadores[1]
    await uow.esperas.add(EsperaEnFranja.crear(ronda.competition_id, ronda.id, primero, ahora))
    await uow.esperas.add(EsperaEnFranja.crear(ronda.competition_id, ronda.id, segundo, ahora))
    await uow.plazas.add(
        PlazaEnFranja.crear(ronda.competition_id, ronda.id, primero, ahora, desde_espera=True)
    )
    await uow.esperas.quitar(ronda.id, primero)
    await db_session.commit()

    esperan = [e.user_id for e in await uow.esperas.de_la_competicion(ronda.competition_id)]
    sin_ver = await uow.plazas.asignadas_sin_ver(primero)
    await uow.plazas.marcar_vista(ronda.id, primero, ahora)
    await uow.esperas.vaciar(ronda.competition_id)
    await db_session.commit()

    assert esperan == [segundo]
    assert [p.desde_espera for p in sin_ver] == [ahora]
    assert await uow.plazas.asignadas_sin_ver(primero) == []
    assert await uow.esperas.de_la_competicion(ronda.competition_id) == []
