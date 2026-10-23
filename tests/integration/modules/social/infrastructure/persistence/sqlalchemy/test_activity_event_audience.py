"""
Tests de integracion: el feed filtra por tipo y visibilidad en el propio SQL.

El filtro tiene que ir en la consulta y no despues: paginar y luego quitar lo
que no se puede ver daria paginas de tamaño irregular.
"""

from datetime import datetime, timedelta
from uuid import uuid4

import pytest

from src.modules.social.domain.entities.activity_event import ActivityEvent
from src.modules.social.domain.repositories.activity_event_repository_interface import (
    ActivitySlice,
)
from src.modules.social.domain.value_objects.activity_event_type import ActivityEventType
from src.modules.social.infrastructure.persistence.sqlalchemy.activity_event_repository import (
    SQLAlchemyActivityEventRepository,
)
from src.modules.user.domain.entities.user import User
from src.modules.user.infrastructure.persistence.sqlalchemy.user_repository import (
    SQLAlchemyUserRepository,
)

pytestmark = pytest.mark.integration

HOY = datetime(2026, 8, 10, 12, 0)
BIRDIE = ActivityEventType.BIRDIE
EAGLE = ActivityEventType.EAGLE_OR_BETTER
HIO = ActivityEventType.HOLE_IN_ONE


def _todos(*user_ids) -> ActivitySlice:
    """Todo lo de esos jugadores, de cualquier tipo y visibilidad."""
    return ActivitySlice(user_ids=tuple(user_ids), types=frozenset(ActivityEventType))


async def _user(db_session) -> User:
    user = User.create(
        first_name="Ana",
        last_name="Garcia",
        email_str=f"aud-{uuid4().hex[:8]}@example.com",
        plain_password="ValidPassword123!",
    )
    await SQLAlchemyUserRepository(db_session).save(user)
    await db_session.commit()
    return user


def _event(user, tipo, match_id, horas=0, visible_to_friends=True) -> ActivityEvent:
    return ActivityEvent.create(
        user_id=user.id,
        type=tipo,
        occurred_at=HOY,
        source_match_id=match_id,
        published_at=HOY + timedelta(hours=horas),
        visible_to_friends=visible_to_friends,
    )


async def test_cada_trozo_trae_solo_sus_tipos_y_jugadores(db_session):
    """
    Given eventos mios y de un amigo de varios tipos / When se piden mis BIRDIE
    y sus EAGLE / Then llegan solo esos, en una sola pagina ordenada.
    """
    yo = await _user(db_session)
    amigo = await _user(db_session)
    repository = SQLAlchemyActivityEventRepository(db_session)
    await repository.add_many(
        [
            _event(yo, BIRDIE, "mio-birdie", horas=1),
            _event(yo, EAGLE, "mio-eagle", horas=2),
            _event(amigo, BIRDIE, "suyo-birdie", horas=3),
            _event(amigo, EAGLE, "suyo-eagle", horas=4),
        ]
    )
    await db_session.commit()

    encontrados = await repository.find_in(
        [
            ActivitySlice(user_ids=(yo.id,), types=frozenset({BIRDIE})),
            ActivitySlice(user_ids=(amigo.id,), types=frozenset({EAGLE})),
        ],
        limit=10,
    )

    assert [e.source_match_id for e in encontrados] == ["suyo-eagle", "mio-birdie"]


async def test_lo_oculto_no_sale_en_el_trozo_de_los_amigos(db_session):
    """
    Given un logro oculto y otro visible / When se piden como amigo y como
    autor / Then el amigo solo recibe el visible y el autor los dos.
    """
    autor = await _user(db_session)
    repository = SQLAlchemyActivityEventRepository(db_session)
    await repository.add_many(
        [
            _event(autor, HIO, "oculto", horas=1, visible_to_friends=False),
            _event(autor, BIRDIE, "visible", horas=2),
        ]
    )
    await db_session.commit()
    tipos = frozenset({HIO, BIRDIE})

    como_amigo = await repository.find_in(
        [ActivitySlice(user_ids=(autor.id,), types=tipos, only_visible_to_friends=True)],
        limit=10,
    )
    como_autor = await repository.find_in(
        [ActivitySlice(user_ids=(autor.id,), types=tipos)], limit=10
    )

    assert [e.source_match_id for e in como_amigo] == ["visible"]
    assert [e.source_match_id for e in como_autor] == ["visible", "oculto"]


async def test_trozos_vacios_no_consultan_nada(db_session):
    """Given trozos sin jugadores o sin tipos / When se piden / Then lista vacia."""
    yo = await _user(db_session)
    repository = SQLAlchemyActivityEventRepository(db_session)
    await repository.add_many([_event(yo, BIRDIE, "m-1")])
    await db_session.commit()

    assert await repository.find_in([], limit=10) == []
    assert (
        await repository.find_in(
            [
                ActivitySlice(user_ids=(), types=frozenset({BIRDIE})),
                ActivitySlice(user_ids=(yo.id,), types=frozenset()),
            ],
            limit=10,
        )
        == []
    )


async def test_ocultar_a_los_amigos_solo_toca_los_tipos_pedidos(db_session):
    """
    Given logros de dos tipos y de dos jugadores / When se ocultan los HIO de
    uno / Then solo esos pasan a ocultos, y se dice cuantos.
    """
    ana = await _user(db_session)
    luis = await _user(db_session)
    repository = SQLAlchemyActivityEventRepository(db_session)
    await repository.add_many(
        [
            _event(ana, HIO, "ana-hio"),
            _event(ana, BIRDIE, "ana-birdie"),
            _event(luis, HIO, "luis-hio"),
        ]
    )
    await db_session.commit()

    ocultos = await repository.hide_from_friends(ana.id, frozenset({HIO}))
    await db_session.commit()

    assert ocultos == 1
    visibles = {
        e.source_match_id: e.visible_to_friends
        for e in await repository.find_in([_todos(ana.id, luis.id)], limit=10)
    }
    assert visibles == {"ana-hio": False, "ana-birdie": True, "luis-hio": True}


async def test_borrar_por_tipos_conserva_los_demas(db_session):
    """Given logros de dos tipos / When se borran los EAGLE / Then el BIRDIE sigue."""
    ana = await _user(db_session)
    repository = SQLAlchemyActivityEventRepository(db_session)
    await repository.add_many([_event(ana, EAGLE, "eagle"), _event(ana, BIRDIE, "birdie")])
    await db_session.commit()

    borrados = await repository.delete_for_user(ana.id, frozenset({EAGLE}))
    await db_session.commit()

    assert borrados == 1
    assert [e.source_match_id for e in await repository.find_in([_todos(ana.id)], limit=10)] == [
        "birdie"
    ]
