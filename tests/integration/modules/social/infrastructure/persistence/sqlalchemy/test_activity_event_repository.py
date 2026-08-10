"""Tests de integracion del repositorio de eventos de actividad."""

from datetime import datetime, timedelta

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

CUANDO = datetime(2026, 8, 10, 12, 0)


async def _make_saved_user(db_session, email: str) -> User:
    user = User.create(
        first_name="Ana",
        last_name="Garcia",
        email_str=email,
        plain_password="ValidPassword123!",
    )
    await SQLAlchemyUserRepository(db_session).save(user)
    await db_session.commit()
    return user


def _event(user, type_, match_id, occurred_at=CUANDO, payload=None) -> ActivityEvent:
    return ActivityEvent.create(
        user_id=user.id,
        type=type_,
        occurred_at=occurred_at,
        source_match_id=match_id,
        payload=payload,
    )


async def test_publica_los_eventos_de_una_vuelta(db_session):
    """Given una vuelta con dos logros / When se publican / Then quedan guardados."""
    user = await _make_saved_user(db_session, "feed-repo-1@example.com")
    repository = SQLAlchemyActivityEventRepository(db_session)

    await repository.add_many(
        [
            _event(user, ActivityEventType.BIRDIE, "match-1", payload={"count": 2}),
            _event(user, ActivityEventType.NEW_COURSE, "match-1"),
        ]
    )
    await db_session.commit()

    encontrados = await repository.find_for_users([user.id], limit=10)

    assert len(encontrados) == 2
    assert {e.type for e in encontrados} == {
        ActivityEventType.BIRDIE,
        ActivityEventType.NEW_COURSE,
    }
    birdie = next(e for e in encontrados if e.type == ActivityEventType.BIRDIE)
    assert birdie.payload == {"count": 2}
    assert birdie.source_match_id == "match-1"


async def test_reprocesar_la_misma_vuelta_no_duplica(db_session):
    """
    Given una vuelta ya publicada / When se vuelve a procesar / Then no se
    repite ninguna entrada en el feed.

    Es el caso del movil reintentando sobre una conexion mala: la peticion llega
    dos veces y el feed no debe enterarse.
    """
    user = await _make_saved_user(db_session, "feed-repo-2@example.com")
    repository = SQLAlchemyActivityEventRepository(db_session)
    logros = [
        _event(user, ActivityEventType.BIRDIE, "match-1", payload={"count": 2}),
        _event(user, ActivityEventType.EAGLE_OR_BETTER, "match-1"),
    ]

    await repository.add_many(logros)
    await db_session.commit()
    # Eventos nuevos (otro id) para el mismo logro: es lo que produciria un
    # segundo procesado de la misma tarjeta
    await repository.add_many(
        [
            _event(user, ActivityEventType.BIRDIE, "match-1", payload={"count": 2}),
            _event(user, ActivityEventType.EAGLE_OR_BETTER, "match-1"),
        ]
    )
    await db_session.commit()

    encontrados = await repository.find_for_users([user.id], limit=10)

    assert len(encontrados) == 2


async def test_el_mismo_logro_en_otra_partida_si_se_publica(db_session):
    """Given dos vueltas con birdies / When se publican / Then hay dos entradas."""
    user = await _make_saved_user(db_session, "feed-repo-3@example.com")
    repository = SQLAlchemyActivityEventRepository(db_session)

    await repository.add_many([_event(user, ActivityEventType.BIRDIE, "match-1")])
    await repository.add_many([_event(user, ActivityEventType.BIRDIE, "match-2")])
    await db_session.commit()

    encontrados = await repository.find_for_users([user.id], limit=10)

    assert len(encontrados) == 2


async def test_el_feed_llega_del_mas_reciente_al_mas_antiguo(db_session):
    """Given eventos de varios dias / When se pide el feed / Then van en orden."""
    user = await _make_saved_user(db_session, "feed-repo-4@example.com")
    repository = SQLAlchemyActivityEventRepository(db_session)

    await repository.add_many(
        [
            _event(user, ActivityEventType.BIRDIE, "match-viejo", CUANDO - timedelta(days=2)),
            _event(user, ActivityEventType.BIRDIE, "match-nuevo", CUANDO),
            _event(user, ActivityEventType.BIRDIE, "match-medio", CUANDO - timedelta(days=1)),
        ]
    )
    await db_session.commit()

    encontrados = await repository.find_for_users([user.id], limit=10)

    assert [e.source_match_id for e in encontrados] == [
        "match-nuevo",
        "match-medio",
        "match-viejo",
    ]


async def test_pagina_por_fecha_y_no_por_numero_de_pagina(db_session):
    """Given un feed largo / When se pide lo anterior a una fecha / Then no repite."""
    user = await _make_saved_user(db_session, "feed-repo-5@example.com")
    repository = SQLAlchemyActivityEventRepository(db_session)
    await repository.add_many(
        [
            _event(user, ActivityEventType.BIRDIE, f"match-{i}", CUANDO - timedelta(days=i))
            for i in range(5)
        ]
    )
    await db_session.commit()

    primera = await repository.find_for_users([user.id], limit=2)
    segunda = await repository.find_for_users(
        [user.id], limit=2, before=primera[-1].occurred_at
    )

    assert [e.source_match_id for e in primera] == ["match-0", "match-1"]
    assert [e.source_match_id for e in segunda] == ["match-2", "match-3"]


async def test_solo_devuelve_lo_de_los_jugadores_pedidos(db_session):
    """Given dos jugadores / When se pide el feed de uno / Then no sale el otro."""
    ana = await _make_saved_user(db_session, "feed-repo-6a@example.com")
    luis = await _make_saved_user(db_session, "feed-repo-6b@example.com")
    repository = SQLAlchemyActivityEventRepository(db_session)

    await repository.add_many([_event(ana, ActivityEventType.BIRDIE, "match-ana")])
    await repository.add_many([_event(luis, ActivityEventType.BIRDIE, "match-luis")])
    await db_session.commit()

    encontrados = await repository.find_for_users([ana.id], limit=10)

    assert [e.source_match_id for e in encontrados] == ["match-ana"]


async def test_sin_jugadores_no_consulta_nada(db_session):
    """Given un jugador sin amigos / When pide el feed / Then llega vacio."""
    repository = SQLAlchemyActivityEventRepository(db_session)

    assert await repository.find_for_users([], limit=10) == []
    assert await repository.count_for_users_since([], since=CUANDO) == 0


async def test_cuenta_lo_publicado_despues_de_una_fecha(db_session):
    """Given eventos antes y despues / When se cuenta / Then solo los de despues."""
    user = await _make_saved_user(db_session, "feed-repo-7@example.com")
    repository = SQLAlchemyActivityEventRepository(db_session)
    await repository.add_many(
        [
            _event(user, ActivityEventType.BIRDIE, "match-antes", CUANDO - timedelta(days=1)),
            _event(user, ActivityEventType.BIRDIE, "match-despues", CUANDO + timedelta(days=1)),
        ]
    )
    await db_session.commit()

    assert await repository.count_for_users_since([user.id], since=CUANDO) == 1


async def test_sabe_si_una_partida_ya_se_publico(db_session):
    """Given una partida publicada / When se pregunta / Then lo sabe."""
    user = await _make_saved_user(db_session, "feed-repo-8@example.com")
    repository = SQLAlchemyActivityEventRepository(db_session)
    await repository.add_many([_event(user, ActivityEventType.BIRDIE, "match-1")])
    await db_session.commit()

    assert await repository.exists_for_match("match-1") is True
    assert await repository.exists_for_match("match-2") is False


async def test_borra_todo_lo_publicado_por_un_jugador(db_session):
    """
    Given dos jugadores con eventos / When uno apaga la publicacion / Then
    desaparece lo suyo y lo del otro sigue.
    """
    ana = await _make_saved_user(db_session, "feed-repo-9a@example.com")
    luis = await _make_saved_user(db_session, "feed-repo-9b@example.com")
    repository = SQLAlchemyActivityEventRepository(db_session)
    await repository.add_many(
        [
            _event(ana, ActivityEventType.BIRDIE, "match-1"),
            _event(ana, ActivityEventType.NEW_COURSE, "match-1"),
        ]
    )
    await repository.add_many([_event(luis, ActivityEventType.BIRDIE, "match-2")])
    await db_session.commit()

    borrados = await repository.delete_for_user(ana.id)
    await db_session.commit()

    assert borrados == 2
    assert await repository.find_for_users([ana.id], limit=10) == []
    assert len(await repository.find_for_users([luis.id], limit=10)) == 1


async def test_publicar_una_lista_vacia_no_hace_nada(db_session):
    """Given una vuelta sin logros / When se publica / Then no falla ni escribe."""
    user = await _make_saved_user(db_session, "feed-repo-10@example.com")
    repository = SQLAlchemyActivityEventRepository(db_session)

    await repository.add_many([])
    await db_session.commit()

    assert await repository.find_for_users([user.id], limit=10) == []
