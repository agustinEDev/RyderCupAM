"""
Los bloqueos que pregunta `user` (avatar y autocompletado), de las amistades de social.

Solo cuenta quien ME bloqueó: lo que yo bloqueé lo sigo viendo (F-09, opción A).
"""

from uuid import uuid4

import pytest

from src.modules.social.domain.entities.friendship import Friendship
from src.modules.social.domain.value_objects.friendship_id import FriendshipId
from src.modules.social.infrastructure.adapters.bloqueos_adapter import BloqueosAdapter
from src.modules.social.infrastructure.persistence.in_memory.in_memory_social_unit_of_work import (
    InMemorySocialUnitOfWork,
)
from src.modules.user.domain.value_objects.user_id import UserId

pytestmark = pytest.mark.asyncio


async def _escena():
    """Uno que me bloqueó, uno al que bloqueé y un amigo."""
    social_uow = InMemorySocialUnitOfWork()
    yo, me_bloqueo, le_bloquee, amigo = (UserId(uuid4()) for _ in range(4))
    async with social_uow:
        await social_uow.friendships.add(
            Friendship.create_blocked(
                id=FriendshipId(uuid4()), blocker_id=me_bloqueo, blocked_id=yo
            )
        )
        await social_uow.friendships.add(
            Friendship.create_blocked(
                id=FriendshipId(uuid4()), blocker_id=yo, blocked_id=le_bloquee
            )
        )
        amistad = Friendship.create(id=FriendshipId(uuid4()), requester_id=yo, addressee_id=amigo)
        amistad.accept()
        await social_uow.friendships.add(amistad)
    return BloqueosAdapter(social_uow), yo, me_bloqueo, le_bloquee, amigo


async def test_me_bloqueo_solo_en_su_sentido():
    """
    Given: Uno me bloqueó, yo bloqueé a otro y tengo un amigo
    When: Se pregunta si cada uno me bloqueó
    Then: Solo el primero
    """
    bloqueos, yo, me_bloqueo, le_bloquee, amigo = await _escena()

    assert await bloqueos.me_bloqueo(yo, me_bloqueo) is True
    assert await bloqueos.me_bloqueo(yo, le_bloquee) is False
    assert await bloqueos.me_bloqueo(yo, amigo) is False
    assert await bloqueos.me_bloqueo(yo, yo) is False


async def test_quienes_me_bloquearon_no_incluye_a_quien_bloquee_yo():
    """
    Given: La misma escena
    When: Se pide quiénes me bloquearon
    Then: Solo quien me bloqueó; y para él, nadie
    """
    bloqueos, yo, me_bloqueo, _, _ = await _escena()

    assert await bloqueos.quienes_me_bloquearon(yo) == frozenset({me_bloqueo})
    assert await bloqueos.quienes_me_bloquearon(me_bloqueo) == frozenset()
