"""
Tests de integracion: el feed se ordena y pagina por fecha de publicacion.

Lo que aqui importa es el SQL de verdad: el orden de los UUID en Postgres y la
comparacion del par (fecha, id) del cursor.
"""

from datetime import datetime, timedelta
from uuid import uuid4

import pytest

from src.modules.social.domain.entities.activity_event import ActivityEvent
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


async def _user(db_session) -> User:
    user = User.create(
        first_name="Ana",
        last_name="Garcia",
        email_str=f"pub-{uuid4().hex[:8]}@example.com",
        plain_password="ValidPassword123!",
    )
    await SQLAlchemyUserRepository(db_session).save(user)
    await db_session.commit()
    return user


def _event(user, match_id, jugado, publicado, visible_to_friends=True) -> ActivityEvent:
    return ActivityEvent.create(
        user_id=user.id,
        type=ActivityEventType.BIRDIE,
        occurred_at=jugado,
        source_match_id=match_id,
        published_at=publicado,
        visible_to_friends=visible_to_friends,
    )


async def test_guarda_y_lee_la_publicacion_y_la_visibilidad(db_session):
    """Given un evento oculto publicado hoy / When se lee / Then conserva ambos campos."""
    user = await _user(db_session)
    repository = SQLAlchemyActivityEventRepository(db_session)
    await repository.add_many(
        [_event(user, "m-1", HOY - timedelta(days=3), HOY, visible_to_friends=False)]
    )
    await db_session.commit()

    [leido] = await repository.find_for_users([user.id], limit=10)

    assert leido.published_at == HOY
    assert leido.occurred_at == HOY - timedelta(days=3)
    assert leido.visible_to_friends is False


async def test_a6_ordena_por_publicacion_y_no_por_juego(db_session):
    """
    A6. Given un torneo jugado hace 5 dias y publicado hoy, y una vuelta de
    ayer publicada ayer / When se pide / Then el torneo va primero.
    """
    user = await _user(db_session)
    repository = SQLAlchemyActivityEventRepository(db_session)
    await repository.add_many(
        [
            _event(user, "ayer", HOY - timedelta(days=1), HOY - timedelta(days=1)),
            _event(user, "torneo", HOY - timedelta(days=5), HOY),
        ]
    )
    await db_session.commit()

    encontrados = await repository.find_for_users([user.id], limit=10)

    assert [e.source_match_id for e in encontrados] == ["torneo", "ayer"]


async def test_a4_misma_publicacion_pagina_por_id_sin_repetir_ni_saltar(db_session):
    """
    A4. Given siete eventos publicados en el mismo instante / When se pagina
    de tres en tres con el cursor (published_at, id) / Then salen los siete,
    una vez cada uno, en orden de id descendente.
    """
    user = await _user(db_session)
    repository = SQLAlchemyActivityEventRepository(db_session)
    eventos = [_event(user, f"m-{i}", HOY - timedelta(days=i), HOY) for i in range(7)]
    await repository.add_many(eventos)
    await db_session.commit()

    vistos, ultimo = [], None
    for _ in range(10):
        pagina = await repository.find_for_users(
            [user.id],
            limit=3,
            before=ultimo.published_at if ultimo else None,
            before_id=ultimo.id if ultimo else None,
        )
        if not pagina:
            break
        vistos.extend(pagina)
        ultimo = pagina[-1]

    assert [e.id for e in vistos] == sorted((e.id for e in eventos), reverse=True)


async def test_a5_un_cursor_de_antes_del_cambio_sigue_valiendo(db_session):
    """
    A5. Given eventos viejos cuyo `published_at` es su `occurred_at` (el
    relleno de la migracion) / When se pagina con un cursor hecho con
    `occurred_at` / Then sigue justo detras.
    """
    user = await _user(db_session)
    repository = SQLAlchemyActivityEventRepository(db_session)
    viejos = [
        _event(user, f"v-{i}", HOY - timedelta(days=i), HOY - timedelta(days=i)) for i in range(4)
    ]
    await repository.add_many(viejos)
    await db_session.commit()

    pagina = await repository.find_for_users(
        [user.id], limit=2, before=viejos[1].occurred_at, before_id=viejos[1].id
    )

    assert [e.source_match_id for e in pagina] == ["v-2", "v-3"]
