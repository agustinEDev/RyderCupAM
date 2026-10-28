"""Los amigos de un jugador, para saber a quién ve en una competición (release social 2)."""

from uuid import uuid4

import pytest

from src.modules.social.domain.entities.friendship import Friendship
from src.modules.social.domain.value_objects.friendship_id import FriendshipId
from src.modules.social.infrastructure.adapters.amigos_adapter import AmigosAdapter
from src.modules.social.infrastructure.persistence.in_memory.in_memory_social_unit_of_work import (
    InMemorySocialUnitOfWork,
)
from src.modules.user.domain.value_objects.user_id import UserId

pytestmark = pytest.mark.asyncio


async def _amistad(uow, a: UserId, b: UserId, *, aceptada: bool = True) -> None:
    amistad = Friendship.create(id=FriendshipId(uuid4()), requester_id=a, addressee_id=b)
    if aceptada:
        amistad.accept()
    async with uow:
        await uow.friendships.add(amistad)


async def test_11_solo_las_amistades_aceptadas_en_los_dos_sentidos():
    uow = InMemorySocialUnitOfWork()
    yo, pidio_el, pedi_yo, pendiente, ajeno = (UserId(uuid4()) for _ in range(5))
    await _amistad(uow, pidio_el, yo)
    await _amistad(uow, yo, pedi_yo)
    await _amistad(uow, yo, pendiente, aceptada=False)
    await _amistad(uow, ajeno, UserId(uuid4()))

    amigos = await AmigosAdapter(uow).ids_de_los_amigos(yo)

    assert amigos == frozenset({pidio_el, pedi_yo})


async def test_sin_amigos_vacio():
    assert (
        await AmigosAdapter(InMemorySocialUnitOfWork()).ids_de_los_amigos(UserId(uuid4()))
        == frozenset()
    )
