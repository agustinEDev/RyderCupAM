"""
El contador de novedades y la papelera de partidas rapidas, en Postgres
(22 oct 2026): `count_in(..., hide_trashed_quick_matches_from=quien_mira)`.

| Caso                                                         | Cuenta |
|--------------------------------------------------------------|--------|
| «Como acabo» y logros de una partida en la papelera del autor | No     |
| Lo mismo, para el propio autor                                | Si     |
| Lo de otro jugador que no la tiene en su papelera             | Si     |
| Un logro de torneo (`from_tournament`) con ese mismo origen   | Si     |
| Un aviso que no sale de partidas rapidas, con ese origen      | Si     |
| Sin pedirlo                                                   | Si     |
"""

from datetime import datetime, timedelta

import pytest

from src.modules.social.domain.entities.activity_event import ActivityEvent
from src.modules.social.domain.repositories.activity_event_repository_interface import (
    ActivitySlice,
)
from src.modules.social.domain.value_objects.activity_event_type import ActivityEventType
from src.modules.social.infrastructure.persistence.sqlalchemy.activity_event_repository import (
    SQLAlchemyActivityEventRepository,
)
from tests.integration.modules.social.infrastructure.persistence.sqlalchemy.test_activity_event_notices import (
    _user,
)
from tests.integration.modules.social.infrastructure.test_shared_games_repositories import (
    _campo,
    _rapida,
)

pytestmark = pytest.mark.integration

T = ActivityEventType
CUANDO = datetime(2026, 10, 22, 12, 0)
TODOS = frozenset(ActivityEventType)


def _evento(user, tipo, origen: str, **payload) -> ActivityEvent:
    return ActivityEvent.create(
        user_id=user.id,
        type=tipo,
        occurred_at=CUANDO,
        source_match_id=origen,
        published_at=CUANDO + timedelta(minutes=1),
        payload=payload,
    )


async def test_the_count_skips_what_the_author_has_in_the_trash(db_session):
    ana, bea, xavi = [await _user(db_session) for _ in range(3)]
    campo = await _campo(db_session, ana.id)
    partida = await _rapida(db_session, campo, ana.id, [bea.id], oculta_por=ana.id)
    origen = str(partida.id.value)
    repository = SQLAlchemyActivityEventRepository(db_session)
    await repository.add_many(
        [
            _evento(ana, T.QUICK_MATCH_FINISHED, origen),
            _evento(ana, T.BIRDIE, origen),
            # Un logro de torneo nunca sale de una partida rapida, aunque coincida el origen
            _evento(ana, T.NEW_COURSE, origen, from_tournament=True),
            # Ni un aviso que no sale de partidas rapidas
            _evento(ana, T.TEE_TIME_ASSIGNED, origen),
            _evento(bea, T.QUICK_MATCH_FINISHED, origen),
        ]
    )
    await db_session.commit()
    trozos = [ActivitySlice(user_ids=(ana.id, bea.id), types=TODOS)]

    async def contar(quien):
        return await repository.count_in(trozos, since=None, hide_trashed_quick_matches_from=quien)

    # Xavi: la de Bea, el aviso y el logro de torneo de Ana (va en la misma tarjeta que
    # su birdie, que si se oculta: la tarjeta de logros es (autor, origen))
    assert await contar(xavi.id) == 3
    # Ana: lo suyo cuenta entero (su «como acabo», su aviso, su tarjeta de logros) y lo de Bea
    assert await contar(ana.id) == 4
    assert await repository.count_in(trozos, since=None) == 4


async def test_another_players_trash_does_not_hide_the_author(db_session):
    ana, bea, xavi = [await _user(db_session) for _ in range(3)]
    campo = await _campo(db_session, ana.id)
    partida = await _rapida(db_session, campo, ana.id, [bea.id], oculta_por=bea.id)
    origen = str(partida.id.value)
    repository = SQLAlchemyActivityEventRepository(db_session)
    await repository.add_many(
        [_evento(ana, T.QUICK_MATCH_FINISHED, origen), _evento(bea, T.QUICK_MATCH_FINISHED, origen)]
    )
    await db_session.commit()

    cuenta = await repository.count_in(
        [ActivitySlice(user_ids=(ana.id, bea.id), types=TODOS)],
        since=None,
        hide_trashed_quick_matches_from=xavi.id,
    )

    assert cuenta == 1
