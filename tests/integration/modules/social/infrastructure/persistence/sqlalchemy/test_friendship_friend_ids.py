"""
Tests de integracion de `find_friend_ids` (BE #176).

Es la consulta que alimenta el feed, y tiene una trampa propia: la amistad se
guarda una sola vez, asi que el usuario puede estar en la columna de quien la
pidio o en la de quien la recibio. Devolver la columna equivocada llenaria el
feed de los propios logros en vez de los de los amigos.
"""

from uuid import uuid4

import pytest

from src.modules.social.domain.entities.friendship import Friendship
from src.modules.social.domain.value_objects.friendship_id import FriendshipId
from src.modules.social.infrastructure.persistence.sqlalchemy.friendship_repository import (
    SQLAlchemyFriendshipRepository,
)
from src.modules.user.domain.entities.user import User
from src.modules.user.infrastructure.persistence.sqlalchemy.user_repository import (
    SQLAlchemyUserRepository,
)

pytestmark = pytest.mark.integration


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


async def _accepted(db_session, requester: User, addressee: User) -> Friendship:
    friendship = Friendship.create(
        id=FriendshipId(uuid4()), requester_id=requester.id, addressee_id=addressee.id
    )
    friendship.accept()
    await SQLAlchemyFriendshipRepository(db_session).add(friendship)
    await db_session.commit()
    return friendship


async def test_devuelve_al_otro_lado_de_la_amistad(db_session):
    """
    Given amistades donde soy el que pidio y donde soy el que recibio / When
    pido mis amigos / Then salen los otros, nunca yo mismo.
    """
    yo = await _make_saved_user(db_session, "ids-1@example.com")
    pedi_yo = await _make_saved_user(db_session, "ids-2@example.com")
    me_pidio = await _make_saved_user(db_session, "ids-3@example.com")
    await _accepted(db_session, yo, pedi_yo)
    await _accepted(db_session, me_pidio, yo)

    amigos = await SQLAlchemyFriendshipRepository(db_session).find_friend_ids(yo.id)

    assert set(amigos) == {pedi_yo.id, me_pidio.id}
    assert yo.id not in amigos


async def test_no_devuelve_las_solicitudes_sin_aceptar(db_session):
    """Given una solicitud pendiente / When pido mis amigos / Then no cuenta."""
    yo = await _make_saved_user(db_session, "ids-4@example.com")
    pendiente = await _make_saved_user(db_session, "ids-5@example.com")
    friendship = Friendship.create(
        id=FriendshipId(uuid4()), requester_id=yo.id, addressee_id=pendiente.id
    )
    await SQLAlchemyFriendshipRepository(db_session).add(friendship)
    await db_session.commit()

    amigos = await SQLAlchemyFriendshipRepository(db_session).find_friend_ids(yo.id)

    assert amigos == []


async def test_sin_amigos_devuelve_vacio(db_session):
    """Given un jugador recien llegado / When pido sus amigos / Then lista vacia."""
    solo = await _make_saved_user(db_session, "ids-6@example.com")

    amigos = await SQLAlchemyFriendshipRepository(db_session).find_friend_ids(solo.id)

    assert amigos == []


async def test_no_pagina_la_lista(db_session):
    """
    Given mas amigos que el limite por defecto de `list_friends` / When pido los
    ids / Then salen todos: el feed no puede dejarse fuera a media lista.
    """
    yo = await _make_saved_user(db_session, "ids-7@example.com")
    esperados = set()
    for i in range(25):
        amigo = await _make_saved_user(db_session, f"ids-7-{i}@example.com")
        await _accepted(db_session, yo, amigo)
        esperados.add(amigo.id)

    amigos = await SQLAlchemyFriendshipRepository(db_session).find_friend_ids(yo.id)

    assert set(amigos) == esperados
    assert len(amigos) == 25
