"""
Un cursor con una fecha en el borde del calendario no tumba la peticion.

Revision de punta a punta (22 oct): `0001-01-01T00:00:00+01:00` y
`9999-12-31T23:59:59-01:00` son fechas validas, pero pasadas a UTC se salen
del calendario y `astimezone` lanzaba `OverflowError`: un 500 en el feed y en
la actividad. La regla ya decidida es que un cursor corrupto da la primera
pagina; estos tambien.
"""

from datetime import datetime, timedelta
from uuid import uuid4

import pytest

from src.modules.golf_course.infrastructure.persistence.in_memory.in_memory_golf_course_unit_of_work import (
    InMemoryGolfCourseUnitOfWork,
)
from src.modules.social.application.feed_cursor import parse_cursor
from src.modules.social.application.games_together import page_of
from src.modules.social.application.ports.shared_games_interface import (
    SharedGame,
    SharedGameKind,
)
from src.modules.social.application.use_cases.get_friends_feed_use_case import (
    GetFriendsFeedUseCase,
)
from src.modules.social.application.use_cases.get_player_activity_use_case import (
    GetPlayerActivityUseCase,
)
from src.modules.social.domain.entities.activity_event import ActivityEvent
from src.modules.social.domain.entities.friendship import Friendship
from src.modules.social.domain.services.head_to_head import Relation
from src.modules.social.domain.value_objects.activity_event_type import ActivityEventType
from src.modules.social.domain.value_objects.friendship_id import FriendshipId
from src.modules.social.infrastructure.persistence.in_memory.in_memory_social_unit_of_work import (
    InMemorySocialUnitOfWork,
)
from src.modules.user.domain.entities.user import User
from src.modules.user.infrastructure.persistence.in_memory.in_memory_unit_of_work import (
    InMemoryUnitOfWork as InMemoryUserUnitOfWork,
)

CUANDO = datetime(2026, 8, 10, 12, 0)

# Validas como fecha, fuera del calendario al pasarlas a UTC
FECHAS_EXTREMAS = ["0001-01-01T00:00:00+01:00", "9999-12-31T23:59:59-01:00"]
CURSORES_EXTREMOS = [f"{fecha}|00000000-0000-0000-0000-000000000000" for fecha in FECHAS_EXTREMAS]


@pytest.mark.parametrize("cursor", CURSORES_EXTREMOS)
def test_el_cursor_extremo_se_lee_como_ninguno(cursor):
    """Given una fecha que se sale al pasarla a UTC / When se lee / Then como sin cursor."""
    assert parse_cursor(cursor) == (None, None)


def test_un_cursor_con_zona_en_el_calendario_sigue_valiendo():
    """El arreglo no se lleva por delante los cursores con zona que si caben."""
    id_ = uuid4()

    assert parse_cursor(f"2026-08-10T14:00:00+02:00|{id_}") == (CUANDO, id_)


async def _escenario():
    social_uow = InMemorySocialUnitOfWork()
    user_uow = InMemoryUserUnitOfWork()
    usuarios = []
    for _ in range(2):
        user = User.create(
            first_name="Ana",
            last_name="Garcia",
            email_str=f"cur_{uuid4().hex[:8]}@test.com",
            plain_password="SecureP@ssw0rd123",
        )
        async with user_uow:
            await user_uow.users.save(user)
        usuarios.append(user)
    yo, amigo = usuarios
    amistad = Friendship.create(id=FriendshipId(uuid4()), requester_id=yo.id, addressee_id=amigo.id)
    amistad.accept()
    async with social_uow:
        await social_uow.friendships.add(amistad)
        await social_uow.activity_events.add_many(
            [
                ActivityEvent.create(
                    user_id=amigo.id,
                    type=ActivityEventType.BIRDIE,
                    occurred_at=CUANDO,
                    source_match_id=f"match-{i}",
                    published_at=CUANDO - timedelta(days=i),
                )
                for i in range(3)
            ]
        )
    return social_uow, user_uow, yo, amigo


@pytest.mark.asyncio
@pytest.mark.parametrize("cursor", CURSORES_EXTREMOS)
async def test_el_feed_con_un_cursor_extremo_da_la_primera_pagina(cursor):
    social_uow, user_uow, yo, _ = await _escenario()
    feed = GetFriendsFeedUseCase(social_uow, user_uow, InMemoryGolfCourseUnitOfWork())

    primera = await feed.execute(str(yo.id.value))
    con_cursor = await feed.execute(str(yo.id.value), cursor=cursor)

    assert [e.id for e in con_cursor.events] == [e.id for e in primera.events]
    assert len(con_cursor.events) == 3


@pytest.mark.asyncio
@pytest.mark.parametrize("cursor", CURSORES_EXTREMOS)
async def test_la_actividad_con_un_cursor_extremo_da_la_primera_pagina(cursor):
    social_uow, user_uow, yo, amigo = await _escenario()
    actividad = GetPlayerActivityUseCase(social_uow, user_uow, InMemoryGolfCourseUnitOfWork())

    pagina = await actividad.execute(str(yo.id.value), str(amigo.id.value), cursor=cursor)

    assert [e.source_match_id for e in pagina.events] == ["match-0", "match-1", "match-2"]


def _partida(dias_atras: int) -> SharedGame:
    return SharedGame(
        kind=SharedGameKind.QUICK_MATCH,
        game_id=str(uuid4()),
        played_on=CUANDO.date() - timedelta(days=dias_atras),
        golf_course_id=None,
        golf_course_name=None,
        format="STABLEFORD",
        relation=Relation.AGAINST,
        outcome=None,
    )


@pytest.mark.parametrize("cursor", CURSORES_EXTREMOS)
def test_partidas_juntos_con_un_cursor_extremo_da_la_primera_pagina(cursor):
    partidas = [_partida(d) for d in range(3)]

    pagina = page_of(partidas, cursor)

    assert [g.id for g in pagina.games] == [p.game_id for p in partidas]
