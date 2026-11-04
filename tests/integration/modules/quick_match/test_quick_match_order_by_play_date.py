"""
El historial y las estadisticas cogen las ultimas partidas por cuando se
jugaron, no por cuando se crearon (Agustin, 24 oct 2026): una creada hace dias
y jugada hoy es la mas reciente.
"""

from datetime import datetime

import pytest

from src.modules.quick_match.infrastructure.persistence.sqlalchemy.quick_match_repository import (
    SQLAlchemyQuickMatchRepository,
)
from tests.integration.modules.competition.infrastructure.persistence.sqlalchemy.test_envelope_repository import (  # noqa: F401
    jugadores,
)
from tests.integration.modules.social.infrastructure.test_shared_games_repositories import (  # noqa: F401
    _campo,
    _rapida,
    campo,
)

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


async def _con_fechas(db_session, match, creada: datetime, empezada: datetime | None):
    match._created_at = creada
    match._started_at = empezada
    await SQLAlchemyQuickMatchRepository(db_session).update(match)
    await db_session.commit()


async def test_the_latest_are_the_last_played(db_session, jugadores, campo):  # noqa: F811
    yo = jugadores[0]
    antigua = await _rapida(db_session, campo, yo, [jugadores[1]])
    nueva = await _rapida(db_session, campo, yo, [jugadores[1]])
    # Creada el lunes y jugada el sabado; la otra, creada y jugada el miercoles
    await _con_fechas(db_session, antigua, datetime(2026, 6, 1, 9), datetime(2026, 6, 6, 9))
    await _con_fechas(db_session, nueva, datetime(2026, 6, 3, 9), datetime(2026, 6, 3, 9))
    repo = SQLAlchemyQuickMatchRepository(db_session)

    historial = await repo.list_for_user(yo, limit=1)
    estadisticas = await repo.list_for_stats(yo, limit=1)

    assert [m.id for m in historial] == [antigua.id]
    assert [m.id for m in estadisticas] == [antigua.id]


async def test_one_never_started_counts_by_its_creation(db_session, jugadores, campo):  # noqa: F811
    yo = jugadores[0]
    sin_empezar = await _rapida(db_session, campo, yo, [jugadores[1]], terminar=False)
    jugada = await _rapida(db_session, campo, yo, [jugadores[1]])
    await _con_fechas(db_session, sin_empezar, datetime(2026, 6, 2, 9), None)
    await _con_fechas(db_session, jugada, datetime(2026, 6, 1, 9), datetime(2026, 6, 4, 9))

    historial = await SQLAlchemyQuickMatchRepository(db_session).list_for_user(yo)

    assert [m.id for m in historial] == [jugada.id, sin_empezar.id]


async def test_f2_by_course_only_that_course_latest_first(db_session, jugadores, campo):  # noqa: F811
    """F2 (4 nov 2026): con un campo, solo las de ese campo, la ultima primero."""
    yo = jugadores[0]
    otro_campo = await _campo(db_session, yo)
    antigua = await _rapida(db_session, campo, yo, [jugadores[1]])
    nueva = await _rapida(db_session, campo, yo, [jugadores[1]])
    fuera = await _rapida(db_session, otro_campo, yo, [jugadores[1]])
    await _con_fechas(db_session, antigua, datetime(2026, 6, 1, 9), datetime(2026, 6, 1, 9))
    await _con_fechas(db_session, nueva, datetime(2026, 6, 3, 9), datetime(2026, 6, 3, 9))
    await _con_fechas(db_session, fuera, datetime(2026, 6, 5, 9), datetime(2026, 6, 5, 9))
    repo = SQLAlchemyQuickMatchRepository(db_session)

    en_el_campo = await repo.list_for_user(yo, golf_course_id=campo.id, limit=5)

    assert [m.id for m in en_el_campo] == [nueva.id, antigua.id]
    assert await repo.count_for_user(yo, golf_course_id=campo.id) == 2


async def test_f2_by_course_counts_beyond_the_page(db_session, jugadores, campo):  # noqa: F811
    """El total es el del campo, no el de la pagina (revisor)."""
    yo = jugadores[0]
    for _ in range(3):
        await _rapida(db_session, campo, yo, [jugadores[1]])
    repo = SQLAlchemyQuickMatchRepository(db_session)

    pagina = await repo.list_for_user(yo, golf_course_id=campo.id, limit=1)

    assert len(pagina) == 1
    assert await repo.count_for_user(yo, golf_course_id=campo.id) == 3


async def test_f2_by_course_keeps_the_other_filters(db_session, jugadores, campo):  # noqa: F811
    """Con el campo siguen mandando el estado, las ocultas y ser participante (revisor)."""
    yo, otro = jugadores[0], jugadores[1]
    tercero = jugadores[2]
    jugada = await _rapida(db_session, campo, yo, [otro])
    await _rapida(db_session, campo, yo, [otro], terminar=False)
    await _rapida(db_session, campo, yo, [otro], oculta_por=yo)
    await _rapida(db_session, campo, otro, [tercero])
    repo = SQLAlchemyQuickMatchRepository(db_session)

    terminadas = await repo.list_for_user(yo, status=jugada.status, golf_course_id=campo.id)

    assert [m.id for m in terminadas] == [jugada.id]
    assert await repo.count_for_user(yo, status=jugada.status, golf_course_id=campo.id) == 1
    # Sin estado: la oculta y la ajena siguen fuera
    assert await repo.count_for_user(yo, golf_course_id=campo.id) == 2
